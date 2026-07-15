# Verbatim from docs/features.md § US-21 (FR-F1 / UC-10). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-F1 @source:UC-10
Feature: Participation and completion funnel report

  Background:
    Given I am signed in as an admin viewing the active challenge

  Scenario: Report shows enrollment and per-week completion
    When I open the participation report
    Then I see total enrollments
    And I see the count of students completing each week
    And the weeks are shown as a funnel

  Scenario: Report reflects new check-ins
    Given a new check-in is recorded for week 4
    When I refresh the report
    Then week 4's completion count increases by one
