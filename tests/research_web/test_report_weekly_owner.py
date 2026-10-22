"""Primary-account authorization is reread before unattended production."""

import json
from types import SimpleNamespace

import pytest

from app.research_web.multiuser.accounts import AccountStore
from app.research_web.report_workflows.models import WorkflowError
from app.research_web.report_workflows.owner import resolve_primary_owner


@pytest.fixture
def owner(tmp_path):
    root = tmp_path / 'research-web'
    root.mkdir()
    server = tmp_path / 'server'
    accounts = AccountStore(server)
    admin = accounts.create_user('admin', 'a private weekly test password', 'admin')
    identity = root.stat()
    record = {'version': 1, 'binding': {
        'primary_user_id': admin.id, 'home': str(tmp_path),
        'data_identity': [identity.st_dev, identity.st_ino],
    }}
    path = server / 'resident.json'
    path.write_text(json.dumps(record))
    path.chmod(0o600)
    return SimpleNamespace(store=SimpleNamespace(root=root)), accounts, admin, path


def test_primary_owner_is_reread_and_revocation_blocks(owner):
    service, accounts, admin, _ = owner
    assert resolve_primary_owner(service)['id'] == admin.id
    accounts.create_user('backupadmin', 'another private weekly password', 'admin')
    accounts.set_enabled(admin.id, False)
    with pytest.raises(WorkflowError, match='主管理员') as failure:
        resolve_primary_owner(service, admin.id)
    assert failure.value.code == 'weekly_owner_unavailable'


def test_another_owner_or_rebound_directory_is_denied(owner):
    service, _, _, path = owner
    with pytest.raises(WorkflowError):
        resolve_primary_owner(service, 'another-account')
    record = json.loads(path.read_text())
    record['binding']['data_identity'][1] += 1
    path.write_text(json.dumps(record))
    with pytest.raises(WorkflowError):
        resolve_primary_owner(service)


def test_missing_binding_does_not_create_account_database(tmp_path):
    root = tmp_path / 'research-web'
    root.mkdir()
    with pytest.raises(WorkflowError):
        resolve_primary_owner(SimpleNamespace(store=SimpleNamespace(root=root)))
    assert not (tmp_path / 'server').exists()
