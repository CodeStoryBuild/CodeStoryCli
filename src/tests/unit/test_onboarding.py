from unittest.mock import patch

from codestory.onboarding import set_ran_onboarding


def test_set_ran_onboarding_creates_parents(tmp_path):
    # tmp_path is a pytest fixture providing a temporary directory
    onboarding_flag = tmp_path / "non_existent_dir" / "onboarding_flag"

    with patch("codestory.onboarding.ONBOARDING_FLAG", onboarding_flag):
        # Ensure the flag and its parent directory don't exist
        assert not onboarding_flag.exists()
        assert not onboarding_flag.parent.exists()

        # Call the function
        set_ran_onboarding()

        # Assert that the directory and flag now exist
        assert onboarding_flag.parent.exists()
        assert onboarding_flag.exists()
