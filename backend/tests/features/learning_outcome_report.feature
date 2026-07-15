# Verbatim from docs/features.md § US-24 (FR-F4 / UC-10). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-F4 @source:UC-10
Feature: Learning-outcome aggregate report

  Scenario: Scores aggregate by outcome tag
    Given quiz responses scored against learning-outcome tags
    When I open the learning-outcome report
    Then I see aggregated scores grouped by outcome tag

  Scenario: Human-overridden scores are included
    Given some reflections were overridden with scored_by "human"
    When I view the aggregate
    Then the overridden scores are reflected in the totals
