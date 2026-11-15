"""Citizen-owned, opt-in emergency information. No medical/risk scoring."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SafetyProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    full_name: str = Field(default='', max_length=100)
    age: int | None = Field(default=None, ge=0, le=120, strict=True)
    phone: str = Field(default='', max_length=24)
    district: str = Field(default='', max_length=100)
    mobility: Literal['unspecified', 'independent', 'limited', 'wheelchair', 'assisted'] = 'unspecified'
    accessibility: list[Literal['vision', 'hearing', 'cognitive']] = Field(default_factory=list, max_length=3)
    transport: Literal['unspecified', 'own', 'needed'] = 'unspecified'
    communication: Literal['unspecified', 'text', 'voice'] = 'unspecified'
    living_alone: bool = False
    dependents: int = Field(default=0, ge=0, le=20, strict=True)
    medical_notes: str = Field(default='', max_length=500)
    contact_name: str = Field(default='', max_length=100)
    contact_phone: str = Field(default='', max_length=24)
    contact_relation: str = Field(default='', max_length=60)
    share_on_sos: bool = False

    @field_validator('phone', 'contact_phone')
    @classmethod
    def phone_format(cls, value):
        if value:
            if any(c not in '+0123456789 ()-' for c in value):
                raise ValueError('invalid_phone')
            if not 7 <= sum(c.isdigit() for c in value) <= 15:
                raise ValueError('invalid_phone')
        return value

    @field_validator('accessibility')
    @classmethod
    def unique_needs(cls, value):
        return sorted(set(value))

    @model_validator(mode='after')
    def complete_contact(self):
        if bool(self.contact_name) != bool(self.contact_phone):
            raise ValueError('contact_name_and_phone_required_together')
        return self


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0, strict=True)
    profile: SafetyProfile


def preparation(profile):
    """Explainable preparation prompts, never an evacuation or clinical decision."""
    needs = []
    if profile['mobility'] in ('limited', 'wheelchair', 'assisted'):
        needs.append('step_free')
    if profile['mobility'] == 'assisted':
        needs.append('companion')
    needs.extend(profile['accessibility'])
    if profile['transport'] == 'needed':
        needs.append('transport')
    if profile['living_alone']:
        needs.append('check_in')
    if profile['dependents']:
        needs.append('dependents')
    if profile['medical_notes']:
        needs.append('medical_note')
    return {'needs': needs, 'route_accessibility': 'unverified'}


def profile_record(store, owner):
    record = store.get('profile', owner)
    profile = record['profile'] if record and record.get('profile') else SafetyProfile().model_dump()
    history = [dict(r) for r in store.db.execute(
        "SELECT action,created FROM audit WHERE target=? AND action LIKE 'profile.%' ORDER BY id DESC LIMIT 8", (owner,))]
    return {'profile': profile, 'version': record['version'] if record else 0,
            'updated_at': record.get('updated_at') if record else None,
            'plan': preparation(profile), 'history': history}


def shared_profiles(store, incident_id):
    """Only currently active reporters with current consent; no historical snapshots."""
    rows = store.db.execute(
        "SELECT r.id,o.data FROM reports r JOIN objects o ON o.id=r.user_id AND o.kind='profile' "
        "JOIN incidents i ON i.id=r.incident_id "
        "WHERE r.incident_id=? AND r.status='active' AND i.status!='resolved' ORDER BY r.created", (incident_id,))
    import json
    result = []
    for row in rows:
        record = json.loads(row['data'])
        profile = record.get('profile')
        if not profile or not profile['share_on_sos']:
            continue
        # Address is not needed: the SOS already carries the reported position.
        details = {k: v for k, v in profile.items() if k not in ('district', 'share_on_sos')}
        result.append({'report_id': row['id'], 'profile': details, 'plan': preparation(profile)})
    return result
