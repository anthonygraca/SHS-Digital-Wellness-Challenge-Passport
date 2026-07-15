# Verbatim from docs/features.md § US-23 (FR-F3 / UC-10). Keep it that way — the
# doc is the contract; this file is the executable copy of it.
@FR-F3 @source:UC-10
Feature: Engagement report

  Scenario: Report shows content views and guide usage
    When I open the engagement report
    Then I see counts of content views
    And I see counts of guide chat sessions
    And both can be viewed per challenge
