from __future__ import annotations

import unittest

from services.skill_evaluation.configurable_review import (
    ConfigurableDistributionReviewer,
    FeatureSet,
    load_profile,
    validate_profile,
)


class ConfigurableDistributionReviewerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile()
        self.reviewer = ConfigurableDistributionReviewer(self.profile)
        self.calibration = {
            name: {"p25": 1, "p50": 2, "p75": 3, "p90": 4}
            for name in self.reviewer._numeric_calibration_features()
        }

    def _feature_set(self, **overrides):
        features = {
            feature["id"]: False if feature["type"] == "boolean" else 0
            for feature in self.profile["features"]
        }
        features.update(overrides)
        return FeatureSet(features=features, metadata_fields=[])

    def test_default_profile_is_valid(self):
        validate_profile(self.profile)

    def test_missing_name_or_description_is_hard_gate(self):
        result = self.reviewer.review(
            feature_set=self._feature_set(
                has_name=False,
                has_description=True,
                description_word_count=10,
                description_has_domain_term=True,
                description_has_action_verb=True,
                description_has_trigger_phrase=True,
            ),
            calibration=self.calibration,
        )
        criterion = next(item for item in result.criteria if item.criterion == "name_description_clarity")
        self.assertEqual(criterion.score, 0)

    def test_examples_apply_bucket_cap_and_quality_bonuses(self):
        result = self.reviewer.review(
            feature_set=self._feature_set(
                example_count=5,
                example_with_context_count=1,
                example_with_output_count=1,
                example_with_code_count=1,
                example_linked_to_rule_count=1,
            ),
            calibration=self.calibration,
        )
        criterion = next(item for item in result.criteria if item.criterion == "examples_clarity")
        self.assertEqual(criterion.score, 10)

    def test_feature_coercion_uses_configured_types_and_defaults(self):
        features = self.reviewer._coerce_features(
            {
                "has_name": "true",
                "description_word_count": "12",
                "schema_term_overlap_count": "2",
            }
        )
        self.assertIs(features["has_name"], True)
        self.assertEqual(features["description_word_count"], 12)
        self.assertEqual(features["schema_term_overlap_count"], 2)
        self.assertIs(features["has_description"], False)


if __name__ == "__main__":
    unittest.main()
