# Verbatim from docs/features.md § US-22 (FR-F2 / UC-10). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-F2 @source:UC-10
Feature: Auto-vs-manual attendance report

  Scenario: Attendance is broken down by method
    When I open the attendance report
    Then I see counts grouped by method: event_qr, staff, and manual
    And the totals reconcile with total check-ins

  Scenario: Auto share is highlighted
    Given most check-ins used event_qr
    When I view the report
    Then the automatically-captured share is shown as a percentage
