# Verbatim from docs/features.md § US-19 (FR-E5 / UC-8). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-E5 @ai @source:UC-8
Feature: AI reflection scoring with human override

  Scenario: Reflection is AI-scored against a rubric
    Given a reflection item with a rubric and a learning-outcome tag
    When I submit a free-text reflection
    Then it is scored against the rubric with short feedback
    And the response is stored with scored_by "auto"

  Scenario: Admin overrides an AI score
    Given an AI-scored reflection
    When an admin adjusts the score
    Then the stored score updates
    And scored_by is set to "human"
