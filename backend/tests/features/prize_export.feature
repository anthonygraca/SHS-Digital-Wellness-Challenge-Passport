# Verbatim from docs/features.md § US-26 (FR-F5 / UC-10). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-F5 @source:UC-10
Feature: Prize-eligible CSV export

  Scenario: Export contains only prize-eligible students
    Given several students, some with all required tasks complete
    When I export the prize-eligible list
    Then the CSV contains only students who completed every required task
    And students missing any required task are excluded

  Scenario: Export reflects derived eligibility
    Given a student just completed their final required task
    When I re-export the list
    Then that student now appears in the CSV
