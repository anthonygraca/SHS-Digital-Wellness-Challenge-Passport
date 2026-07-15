# Verbatim from docs/features.md § US-18 (FR-E4 / UC-8). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-E4 @source:UC-8
Feature: MCQ auto-scoring

  Scenario: Correct answer is scored instantly
    Given an MCQ with a defined answer key
    When I submit the correct option
    Then I see an instant correct result
    And the score is stored against the learning-outcome tag

  Scenario: Incorrect answer is scored instantly with feedback
    When I submit an incorrect option
    Then I see an instant incorrect result
    And the score is stored against the learning-outcome tag
