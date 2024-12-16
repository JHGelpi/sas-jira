def affects_version_missing():
    '''
    Fields that should be considered when looking at Jira hygiene:
    - status (issue.fields.status.name if issue.fields.status else 'No Status')
    - type (issue.fields.issuetype if issue.fields.issuetype else 'No Type')
    - sprint data
        - sprint_data_string = getattr(issue.fields, 'customfield_10102', 'No Data')
        - sprint_data_list.append((issue.key, sprint_data_string))
        - parsed_sprint_data = parse_sprint_data(sprint_data_string, folder_trunk)
        - sprint_start_date = format_date(parsed_sprint_data[1])
        - sprint_end_date = format_date(parsed_sprint_data[2])
        - completed_date = format_date(parsed_sprint_data[5])
    - requirement (req_link = getattr(issue.fields, 'customfield_15703', ''))
    - epic (epic_link = getattr(issue.fields, 'customfield_10301', ''))
    - updated date (updatedDate = issue.fields.updated if issue.fields.updated else '1900-12-31')
    '''
    '''
    issuetype = bug and ("Pipeline Discovery Stage" = shipped or Origin in (CRP, ICRP, BRP)) and affectedVersion is empty and sprint in openSprints(	
    '''
    '''
    Check to see if a requirement/epic is linked as long as the jira type is Story/Task/Bug/Epic
    req_link = getattr(issue.fields, 'customfield_15703', '')
    '''