from app.services.archiver import determine_new_status, MISSING_THRESHOLD


def test_active_listing_stays_active():
    assert determine_new_status("ACTIVE", found_in_search=True, detail_exists=True, missing_count=0) == "ACTIVE"


def test_new_listing_becomes_active():
    assert determine_new_status("NEW", found_in_search=True, detail_exists=True, missing_count=0) == "ACTIVE"


def test_missing_once_becomes_missing():
    assert determine_new_status("ACTIVE", found_in_search=False, detail_exists=True, missing_count=0) == "MISSING_ON_SEARCH"


def test_missing_threshold_becomes_unavailable():
    assert determine_new_status("MISSING_ON_SEARCH", found_in_search=False, detail_exists=True, missing_count=MISSING_THRESHOLD) == "UNAVAILABLE"


def test_detail_gone_becomes_archived():
    assert determine_new_status("ACTIVE", found_in_search=False, detail_exists=False, missing_count=0) == "ARCHIVED"


def test_reappeared_after_missing():
    assert determine_new_status("MISSING_ON_SEARCH", found_in_search=True, detail_exists=True, missing_count=2) == "REAPPEARED"


def test_saved_listing_not_changed_by_scan():
    assert determine_new_status("SAVED", found_in_search=True, detail_exists=True, missing_count=0) == "SAVED"


def test_saved_listing_still_archived_if_detail_gone():
    assert determine_new_status("SAVED", found_in_search=False, detail_exists=False, missing_count=0) == "ARCHIVED"
