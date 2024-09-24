# Summary
This document will be used to capture the fields I am utilizing out of Jira and my understanding/definition of said fields.  I also intend on documenting what some of the example use cases are for the fields.

# API Information
Jira Server URL: https://rndjira.sas.com/

# Jira Fields Used
- issue.fields, 'customfield_10301': This is intended to capture the Epic Link
- issue.fields, 'customfield_16301': This is used to capture the Parent Link
- issue.fields, 'customfield_10102': This is a string that captures sprint data
- issue.fields.issuetype: This is the issue type
- issue.fields.assignee.displayName: This is the assignee
- issue.fields.status.name: This is the status
- issue.key: Issue key
- issue.fields, 'labels': All of the labels attached to a given issue
- issue.fields, 'customfield_15600': Pipeline stage
- issue.fields, 'customfield_14504': Bug origin
- issue.fields, 'fixVersions': Fix version
- issue.fields, 'components': Components
- escaped_bug: Calculated field.  If Origin is CRP and pipeline stage is "shipped" then 'Y'
- triage_flg: Calculated field.  If label exists that has the value of `collector-59dc380c` then 'Y'
# Audit rules
- Presence of fixVersion/s value if work is in a sprint
- Presence of a parent link/is related link
- Presence of Affects Version/s if jira type is a Bug
- Age of last update of Bug jira type
