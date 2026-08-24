"""Validation and generation rules for client-facing employee alias names.

Rules implemented here (as specified by the business):
1. An alias name must share the same first/last initials as the employee's
   real name, and should read as a plausible western (US) name.
2. The client email is derived from the alias: first letter of the alias
   first name + the complete alias last name (any middle name is ignored --
   and an alias itself may not contain a middle name).
3/4. The (first-initial, last-name) pairing behind that email must be
   globally unique across every alias in the system, regardless of what the
   rest of the first name is.
5. Every alias -- whether picked from a suggestion or typed by hand -- is
   run through the same checks before it's accepted.
"""

import re
from difflib import SequenceMatcher

from .alias_names_data import FIRST_NAMES, LAST_NAMES

CLIENT_EMAIL_DOMAIN = 'aeis.com'

_NAME_TOKEN_RE = re.compile(r"^[A-Za-z](?:[A-Za-z'-]*[A-Za-z])?$")


class AliasError(Exception):
    """Raised when an alias name violates one of the alias rules."""


def split_two_word_name(name):
    """Return (first, last) for a name that must be exactly two words.

    Rejects single-word names and anything with a middle name -- an alias
    is not allowed to carry one, even if the employee's real name does.
    """
    tokens = (name or '').split()
    if len(tokens) != 2:
        raise AliasError('Alias name must be exactly a first and last name, with no middle name.')
    first, last = tokens
    if not (_NAME_TOKEN_RE.match(first) and _NAME_TOKEN_RE.match(last)):
        raise AliasError('Alias name must only contain letters.')
    return first, last


def initials_of(full_name):
    """Return (first_initial, last_initial) of a real name, ignoring any middle names."""
    tokens = (full_name or '').split()
    if not tokens:
        raise AliasError('Employee full name is required to validate an alias.')
    return tokens[0][0].upper(), tokens[-1][0].upper()


def derive_client_email(alias_name, domain=CLIENT_EMAIL_DOMAIN):
    """Rule 2: first letter of alias first name + full alias last name."""
    first, last = split_two_word_name(alias_name)
    local_part = f'{first[0]}{last}'.lower()
    local_part = re.sub(r"[^a-z]", '', local_part)
    return f'{local_part}@{domain}'


def _email_taken(client_email, *, exclude_employee_id=None, exclude_profile_id=None):
    """Look up whether client_email is already assigned, anywhere in the system.

    Checks both the new Employee.client_email column and the legacy
    official_email fields -- plenty of existing records already carry a
    client-style email (e.g. "Alex Brooks" -> abrooks@aeis.com) typed in by
    hand before this checker existed, and those must count as taken too.
    """
    from django.db.models import Q

    from apps.employees.models import Employee
    from apps.organisations.models import OrganisationMemberProfile

    employee_qs = Employee.objects.filter(
        Q(client_email__iexact=client_email) | Q(official_email__iexact=client_email)
    )
    if exclude_employee_id is not None:
        employee_qs = employee_qs.exclude(pk=exclude_employee_id)
    employee_match = employee_qs.first()
    if employee_match:
        return employee_match.full_name

    profile_qs = OrganisationMemberProfile.objects.filter(official_email__iexact=client_email)
    if exclude_profile_id is not None:
        profile_qs = profile_qs.exclude(pk=exclude_profile_id)
    profile_match = profile_qs.select_related('employee').first()
    if profile_match:
        return profile_match.employee.full_name

    return None


def check_alias(full_name, alias_name, *, exclude_employee_id=None, exclude_profile_id=None):
    """Validate an alias against all rules and return its derived client email.

    full_name is optional: pass it to also enforce the initials-match rule
    (rule 1) against a specific employee; omit it to just check the alias's
    structure and derived-email availability (used by the standalone Alias
    Name Checker, which may not have a real name attached yet).

    Raises AliasError on any violation.
    """
    if not (alias_name or '').strip():
        raise AliasError('Alias name is required.')

    alias_first, alias_last = split_two_word_name(alias_name)

    # Initials only need to match when a real name is given to match against.
    # The standalone Alias Name Checker lets an admin look up an alias name's
    # email availability on its own, with no employee attached yet.
    if (full_name or '').strip():
        alias_initials = (alias_first[0].upper(), alias_last[0].upper())
        real_initials = initials_of(full_name)
        if alias_initials != real_initials:
            raise AliasError(
                f'Alias name must share the initials {real_initials[0]}.{real_initials[1]}. '
                f'with the employee\'s real name.'
            )

    client_email = derive_client_email(alias_name)
    holder = _email_taken(
        client_email,
        exclude_employee_id=exclude_employee_id,
        exclude_profile_id=exclude_profile_id,
    )
    if holder:
        raise AliasError(
            f'{client_email} is already in use (first initial + last name must be globally unique) -- '
            f'held by {holder}.'
        )

    return client_email


def suggest_aliases(full_name, limit=6):
    """Rule 1/3: suggest western-name aliases matching the employee's initials.

    Ranked by closeness to the original name, filtered to only names whose
    derived client email is not already taken anywhere in the system.
    """
    tokens = (full_name or '').split()
    if not tokens:
        return []

    first_initial, last_initial = initials_of(full_name)
    orig_first, orig_last = tokens[0].lower(), tokens[-1].lower()

    candidates = []
    for candidate_first in FIRST_NAMES.get(first_initial, []):
        first_score = SequenceMatcher(None, candidate_first.lower(), orig_first).ratio()
        for candidate_last in LAST_NAMES.get(last_initial, []):
            last_score = SequenceMatcher(None, candidate_last.lower(), orig_last).ratio()
            candidates.append((first_score + last_score, candidate_first, candidate_last))

    candidates.sort(key=lambda item: item[0], reverse=True)

    suggestions = []
    seen_emails = set()
    for _, candidate_first, candidate_last in candidates:
        alias_name = f'{candidate_first} {candidate_last}'
        client_email = derive_client_email(alias_name)
        # Two suggestions sharing a (first-initial, last-name) pair would
        # collide with each other -- only the first (closest-matching) one
        # for a given derived email is worth offering.
        if client_email in seen_emails:
            continue
        if _email_taken(client_email):
            continue
        seen_emails.add(client_email)
        suggestions.append({'alias_name': alias_name, 'client_email': client_email})
        if len(suggestions) >= limit:
            break

    return suggestions
