from app.audit.service import verify_chain_integrity, write_audit_event


def test_empty_chain_is_valid(db_session):
    assert verify_chain_integrity(db_session) is True


def test_chain_stays_valid_after_multiple_writes(db_session):
    write_audit_event(db_session, "USER_LOGIN", event_metadata={"n": 1})
    write_audit_event(db_session, "USER_LOGIN", event_metadata={"n": 2})
    write_audit_event(db_session, "USER_LOGOUT", event_metadata={"n": 3})
    db_session.commit()
    assert verify_chain_integrity(db_session) is True


def test_tampering_breaks_chain(db_session):
    entry = write_audit_event(db_session, "USER_LOGIN")
    db_session.commit()
    entry.event_type = "TAMPERED"
    db_session.commit()
    assert verify_chain_integrity(db_session) is False
