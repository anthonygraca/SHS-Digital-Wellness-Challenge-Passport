# Verbatim from docs/features.md § US-27 (FR-D6 / UC-11). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-D6 @audit @source:UC-11
Feature: Manual completion override with audit

  Background:
    Given I am signed in as an admin

  Scenario: Admin manually marks a completion
    When I manually mark a student complete for "Week 2 - Nutrition"
    Then a check-in is recorded with method "manual"
    And the audit trail records my identity, the timestamp, and a reason

  Scenario: Admin overrides an existing completion
    Given a student has an erroneous completion for "Week 2 - Nutrition"
    When I remove or correct it
    Then the change is recorded in the audit trail
    And the prior state is preserved for audit
