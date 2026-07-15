# Verbatim from docs/features.md § US-14 (FR-B6 / UC-5). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-B6 @source:UC-5
Feature: Duplicate prior challenge

  Scenario: Duplicate creates an editable draft
    Given a prior challenge "Fall 2025 - Stranger Things"
    When I duplicate it
    Then a new draft challenge is created with the same tasks, quiz items, and theme
    And the copy is independent of the original

  Scenario: Editing the copy does not affect the original
    Given a duplicated draft challenge
    When I change a task in the copy
    Then the original challenge is unchanged
