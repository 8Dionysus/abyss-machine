from __future__ import annotations
import errno
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from abyss_machine import storage_health as health, storage_forecast


def btrfs_fixture(root, *, pending, spare=1024**2):
    gib=1024**3
    values={'total_bytes':4*gib,'bytes_used':int(3.5*gib),'bytes_reserved':0,
            'bytes_pinned':0,'bytes_may_use':pending,'bytes_readonly':0,'chunk_size':gib,'disk_total':8*gib}
    for key,value in values.items():
        p=root/'allocation/metadata'/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(value))
    for kind,value in [('data',180*gib),('system',16*1024**2)]:
        p=root/'allocation'/kind/'disk_total';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(value))
    p=root/'devices/device/size';p.parent.mkdir(parents=True);p.write_text(str((188*gib+16*1024**2+spare)//512))


def test_metadata_reservations_trigger_critical_despite_free_data(tmp_path):
    btrfs_fixture(tmp_path,pending=600*1024**2)
    result=health.btrfs_allocation(tmp_path)
    assert result['status']=='critical'
    assert result['metadata_headroom_bytes']==0
    assert result['unallocated_device_bytes']==1024**2
    assert result['automatic_remediation'] is False


def test_unallocated_device_headroom_distinguishes_metadata_pressure(tmp_path):
    btrfs_fixture(tmp_path,pending=300*1024**2,spare=8*1024**3)
    assert health.btrfs_allocation(tmp_path)['status']=='ok'


def test_enospc_alarm_survives_normal_history_failure(monkeypatch,tmp_path):
    monkeypatch.setattr(storage_forecast,'_measure',lambda path,timestamp: {'path':str(path),'timestamp':timestamp,'filesystem_key':'one','available_to_user_bytes':31*1024**3})
    def full(*args):raise OSError(errno.ENOSPC,'test filesystem full')
    monkeypatch.setattr(storage_forecast,'_write',full)
    report=storage_forecast.observe(tmp_path/'capacity.json',paths=(Path('/'),))
    assert report['errno']==errno.ENOSPC
    result=health.publish(report,runtime_root=tmp_path/'run',emergency_root=tmp_path/'independent',notify=False)
    assert result['severity']=='critical'
    assert json.loads((tmp_path/'run/last-alert.json').read_text())['severity']=='critical'
    assert (tmp_path/'independent/last-alert.json').is_file()
    health.publish({'ok':True,'roots':[]},runtime_root=tmp_path/'run',emergency_root=tmp_path/'independent',notify=False)
    assert json.loads((tmp_path/'run/latest.json').read_text())['severity']=='ok'
    assert json.loads((tmp_path/'run/last-alert.json').read_text())['severity']=='critical'


def test_one_failed_alert_sink_does_not_block_other_sink(monkeypatch,tmp_path):
    real=health.atomic_json
    def write(path,value):
        if path.is_relative_to(tmp_path/'run'):raise OSError(errno.ENOSPC,'full')
        real(path,value)
    monkeypatch.setattr(health,'atomic_json',write)
    result=health.publish({'ok':False,'errno':errno.ENOSPC},runtime_root=tmp_path/'run',emergency_root=tmp_path/'independent',notify=False)
    assert result['severity']=='critical' and result['delivery_errors']
    assert (tmp_path/'independent/last-alert.json').is_file()


def test_failed_channels_retry_without_repeating_successful_channels(monkeypatch,tmp_path):
    real=health.atomic_json
    writes=[]
    notifications=[]
    failed_once=set()
    def write(path,value):
        if path==tmp_path/'independent/last-alert.json' and path not in failed_once:
            failed_once.add(path)
            raise OSError(errno.ENOSPC,'full')
        writes.append(path)
        real(path,value)
    def notify(*args,**kwargs):
        notifications.append(args)
        if len(notifications)==1:
            raise OSError('notification unavailable')
    monkeypatch.setattr(health,'atomic_json',write)
    monkeypatch.setattr(health.subprocess,'run',notify)
    for _ in range(3):
        health.publish({'ok':False,'errno':errno.ENOSPC},runtime_root=tmp_path/'run',emergency_root=tmp_path/'independent')
    assert writes.count(tmp_path/'run/last-alert.json')==1
    assert writes.count(tmp_path/'independent/last-alert.json')==1
    assert len(notifications)==2


def test_warning_does_not_claim_a_write_has_already_failed(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(health.subprocess,'run',lambda args,**kwargs:calls.append(args))
    health.publish({'ok':True,'roots':[{'path':'/','filesystem_health':{'status':'critical','reason':'btrfs_allocation_headroom_low'}}]},runtime_root=tmp_path/'run',emergency_root=tmp_path/'independent')
    assert calls[0][-2]=='Недостаточно резерва файловой системы'
    assert calls[0][-1]=='Под угрозой сохранение данных на разделе /.'
