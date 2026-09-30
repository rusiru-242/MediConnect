from enum import Enum
from typing import List


class DoctorSpecialty(str, Enum):
    """Centralized supported medical specialties for MediConnect."""

    GENERAL_PRACTITIONER = "General Practitioner"
    GENERAL_PHYSICIAN = "General Physician"
    PEDIATRICIAN = "Pediatrician"
    CARDIOLOGIST = "Cardiologist"
    DERMATOLOGIST = "Dermatologist"
    NEUROLOGIST = "Neurologist"
    PSYCHIATRIST = "Psychiatrist"
    GYNECOLOGIST = "Gynecologist"
    ENT_SPECIALIST = "ENT Specialist"
    OPHTHALMOLOGIST = "Ophthalmologist"
    ORTHOPEDIC_SURGEON = "Orthopedic Surgeon"
    GENERAL_SURGEON = "General Surgeon"
    ENDOCRINOLOGIST = "Endocrinologist"
    GASTROENTEROLOGIST = "Gastroenterologist"
    PULMONOLOGIST = "Pulmonologist"
    NEPHROLOGIST = "Nephrologist"
    UROLOGIST = "Urologist"


SUPPORTED_SPECIALTIES: List[str] = [specialty.value for specialty in DoctorSpecialty]


def is_valid_specialty(specialty: str) -> bool:
    """Check if the provided specialty matches a supported category."""
    if not specialty or not isinstance(specialty, str):
        return False
    return specialty.strip() in SUPPORTED_SPECIALTIES
