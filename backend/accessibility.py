"""Conservative accessibility contract shared by routes and SOS priority.

Seed verification is simulation-only, never a claim about surveyed Baku roads.
Unknown attributes fail closed. Role selection is a self-declared support need.
"""
CITIZEN_ROLES = ('citizen', 'priority_citizen')


def needs_accessible(profile):
    return profile.get('mobility') in ('limited', 'wheelchair', 'assisted')


def accessible(item):
    return all(item.get(key) is True for key in (
        'accessibility_verified', 'step_free', 'ramp_access',
        'obstacle_free', 'wheelchair_accessible', 'medical_vehicle_accessible'))
