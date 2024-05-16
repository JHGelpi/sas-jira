from jira import JIRA
#import csv
#from datetime import datetime

def parse_component_data(components):
    if not components:
        return ''

    # Initialize a list to store component names
    component_names = []

    # Iterate over each component in the list
    for component in components:
        # Check if the component has a name attribute
        if hasattr(component, 'name') and component.name:
            component_names.append(component.name)
        else:
            component_names.append('No Component Name')

    # Join all component names into a single string separated by commas
    return '|'.join(component_names)

def parse_fix_version_data(components):
    if not components:
        return ''

    # Initialize a list to store component names
    component_names = []

    # Iterate over each component in the list
    for component in components:
        # Check if the component has a name attribute
        if hasattr(component, 'name') and component.name:
            component_names.append(component.name)
        else:
            component_names.append('')

    # Join all component names into a single string separated by commas
    return '|'.join(component_names)

'''def parse_label_data(labels):
    if not labels:
        return ''
    
    # Initialize a list to store label names
    label_names = []

    # Iterate over each label in the list

    for label in labels:
        label_names.append(labels)
    
    return '|'.join(label_names)'''
def parse_label_data(labels):
    if not labels:
        return ''
    
    # Initialize a list to store label names
    label_names = []

    # Iterate over each label in the list
    for label in labels:
        # Ensure that label is a string, if the label structure is simple and contains direct string items
        label_names.append(str(label))  # Converts label to string if it's not already
    
    return '|'.join(label_names)
