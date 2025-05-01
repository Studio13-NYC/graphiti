import sys
from typing import Any, Optional, Union, List, Dict

# Add parent directory to sys.path to allow imports from graphiti_core
# This might be necessary depending on how the server is run.
# Consider better packaging solutions for broader distribution.
# parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# if parent_dir not in sys.path:
#     sys.path.append(parent_dir)

from pydantic import BaseModel, Field

# Base Entities (retained for compatibility)
class Requirement(BaseModel):
    """A Requirement represents a specific need, feature, or functionality that a product or service must fulfill."""
    project_name: str = Field(..., description='The name of the project to which the requirement belongs.')
    description: str = Field(..., description='Description of the requirement.')

class Preference(BaseModel):
    """A Preference represents a user's expressed like, dislike, or preference for something."""
    category: str = Field(..., description="The category of the preference. (e.g., 'Brands', 'Food', 'Music')")
    description: str = Field(..., description='Brief description of the preference.')

class Procedure(BaseModel):
    """A Procedure informing the agent what actions to take or how to perform in certain scenarios."""
    description: str = Field(..., description='Brief description of the procedure.')


# ── Music Entity Models ────────────────────────────────────
class Artist(BaseModel):
    """An individual musician or group that creates musical content."""
    name: str = Field(..., description="Artist name")
    biography: Optional[str] = Field(None, description="Artist biography and background")
    genres: Optional[List[str]] = Field(None, description="List of musical genres associated with this artist")
    active_years: Optional[str] = Field(None, description="Time period when artist was/is active")
    country: Optional[str] = Field(None, description="Country of origin")
    image_url: Optional[str] = Field(None, description="URL to artist image")
    influences: Optional[List[str]] = Field(None, description="Artists that influenced this artist")
    popularity: Optional[int] = Field(None, description="Popularity score (0-100)")
    followers: Optional[int] = Field(None, description="Number of followers/fans")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI for this artist")
    spotify_url: Optional[str] = Field(None, description="Spotify URL for this artist")
    # Extended fields for future compatibility
    social_media: Optional[Dict[str, str]] = Field(None, description="Social media handles/links")
    official_website: Optional[str] = Field(None, description="Artist's official website")
    formation_date: Optional[str] = Field(None, description="When band/group was formed")
    disbandment_date: Optional[str] = Field(None, description="When band/group dissolved")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Album(BaseModel):
    """A collection of music tracks released together."""
    title: str = Field(..., description="Album title")
    release_date: Optional[str] = Field(None, description="Date album was released")
    album_type: Optional[str] = Field(None, description="Type of album (LP, EP, Single, Compilation, etc.)")
    total_tracks: Optional[int] = Field(None, description="Total number of tracks")
    catalog_number: Optional[str] = Field(None, description="Album's catalog number")
    images: Optional[List[Dict[str, str]]] = Field(None, description="Album artwork URLs")
    release_date_precision: Optional[str] = Field(None, description="Precision of the release date (day, month, year)")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI for this album")
    spotify_url: Optional[str] = Field(None, description="Spotify URL for this album")
    # Extended fields for future compatibility
    rating: Optional[float] = Field(None, description="Average rating (0.0-5.0)")
    genres: Optional[List[str]] = Field(None, description="Album genres")
    description: Optional[str] = Field(None, description="Album description/context")
    producer: Optional[str] = Field(None, description="Album producer")
    length_minutes: Optional[int] = Field(None, description="Total album length in minutes")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Track(BaseModel):
    """An individual song or musical composition."""
    title: str = Field(..., description="Track title")
    duration_ms: Optional[int] = Field(None, description="Duration in milliseconds")
    explicit: Optional[bool] = Field(None, description="Whether track contains explicit content")
    popularity: Optional[int] = Field(None, description="Popularity score (0-100)")
    preview_url: Optional[str] = Field(None, description="URL to track preview")
    isrc: Optional[str] = Field(None, description="International Standard Recording Code")
    lyrics: Optional[str] = Field(None, description="Track lyrics")
    tempo: Optional[float] = Field(None, description="Tempo in BPM")
    key: Optional[str] = Field(None, description="Musical key of the track")
    genre: Optional[str] = Field(None, description="Primary genre")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI")
    spotify_url: Optional[str] = Field(None, description="Spotify URL")
    # Extended fields for future compatibility
    mood: Optional[List[str]] = Field(None, description="Mood descriptors")
    release_date: Optional[str] = Field(None, description="Track release date if different from album")
    writers: Optional[List[str]] = Field(None, description="Songwriters")
    producers: Optional[List[str]] = Field(None, description="Track producers")
    recording_date: Optional[str] = Field(None, description="When track was recorded")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Equipment(BaseModel):
    """Musical instrument or gear used in recording or performance."""
    name: str = Field(..., description="Equipment name")
    type: Optional[str] = Field(None, description="Equipment type (guitar, synthesizer, etc.)")
    manufacturer: Optional[str] = Field(None, description="Equipment manufacturer")
    model: Optional[str] = Field(None, description="Model designation")
    year: Optional[int] = Field(None, description="Year of manufacture")
    specifications: Optional[Dict[str, Union[str, int, float]]] = Field(None, description="Technical specifications")
    notable_users: Optional[List[str]] = Field(None, description="Notable musicians who use this equipment")
    # Extended fields for future compatibility
    description: Optional[str] = Field(None, description="Detailed description")
    image_url: Optional[str] = Field(None, description="Equipment image URL")
    serial_number: Optional[str] = Field(None, description="Specific serial number if relevant")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Studio(BaseModel):
    """Recording facility where music is produced."""
    name: str = Field(..., description="Studio name")
    location: Optional[str] = Field(None, description="Studio location")
    founding_date: Optional[str] = Field(None, description="When studio was founded")
    specifications: Optional[Dict[str, Union[str, int, float]]] = Field(None, description="Technical specifications")
    notable_recordings: Optional[List[str]] = Field(None, description="Famous recordings made at this studio")
    # Extended fields for future compatibility
    address: Optional[str] = Field(None, description="Full address")
    engineers: Optional[List[str]] = Field(None, description="Notable engineers who work here")
    equipment: Optional[List[str]] = Field(None, description="Notable equipment available")
    image_url: Optional[str] = Field(None, description="Studio image URL")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Person(BaseModel):
    """Individual involved in music production (producer, engineer, etc.)."""
    name: str = Field(..., description="Person's name")
    roles: Optional[List[str]] = Field(None, description="Professional roles")
    biography: Optional[str] = Field(None, description="Biographical information")
    specialties: Optional[List[str]] = Field(None, description="Areas of specialty")
    notable_works: Optional[List[str]] = Field(None, description="Notable works/projects")
    # Extended fields for future compatibility
    birth_date: Optional[str] = Field(None, description="Date of birth")
    country: Optional[str] = Field(None, description="Country of origin")
    image_url: Optional[str] = Field(None, description="Person's image URL")
    awards: Optional[List[str]] = Field(None, description="Awards received")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Credit(BaseModel):
    """Attribution for contribution to a musical work."""
    role_name: str = Field(..., description="Specific role name")
    contribution_details: Optional[str] = Field(None, description="Details about the contribution")
    primary_credit: Optional[bool] = Field(None, description="Whether this is a primary credit")
    contribution_percentage: Optional[float] = Field(None, description="Percentage of contribution if applicable")
    # Extended fields for future compatibility
    dates: Optional[str] = Field(None, description="When the contribution occurred")
    notes: Optional[str] = Field(None, description="Additional notes about this credit")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Label(BaseModel):
    """Music publishing company or record label."""
    name: str = Field(..., description="Label name")
    founding_date: Optional[str] = Field(None, description="When label was founded")
    parent_company: Optional[str] = Field(None, description="Parent company if applicable")
    roster: Optional[List[str]] = Field(None, description="Current artist roster")
    genre_focus: Optional[List[str]] = Field(None, description="Genres the label focuses on")
    # Extended fields for future compatibility
    headquarters: Optional[str] = Field(None, description="Headquarters location")
    founder: Optional[str] = Field(None, description="Label founder")
    logo_url: Optional[str] = Field(None, description="Label logo URL")
    website: Optional[str] = Field(None, description="Official website")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Performance(BaseModel):
    """Live musical performance or concert."""
    venue: str = Field(..., description="Performance venue")
    date: Optional[str] = Field(None, description="Performance date")
    setlist: Optional[List[str]] = Field(None, description="List of tracks performed")
    lineup: Optional[List[str]] = Field(None, description="Artists who performed")
    recordings: Optional[List[str]] = Field(None, description="Available recordings of this performance")
    # Extended fields for future compatibility
    tour_name: Optional[str] = Field(None, description="Name of tour if applicable")
    attendance: Optional[int] = Field(None, description="Number of attendees")
    duration_minutes: Optional[int] = Field(None, description="Performance length in minutes")
    media_coverage: Optional[List[str]] = Field(None, description="Media coverage links")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support")


class Effect(BaseModel):
    """Audio effect or signal processor used in production."""
    name: str = Field(..., description="Effect name")
    type: Optional[str] = Field(None, description="Effect type (reverb, delay, etc.)")
    parameters: Optional[Dict[str, Union[str, int, float]]] = Field(None, description="Effect parameters")
    position: Optional[str] = Field(None, description="Position in signal chain")
    context: Optional[str] = Field(None, description="How the effect was used")
    # Extended fields for future compatibility
    hardware: Optional[bool] = Field(None, description="Whether this is hardware (vs software)")
    manufacturer: Optional[str] = Field(None, description="Effect manufacturer")
    model: Optional[str] = Field(None, description="Model name/number")
    release_year: Optional[int] = Field(None, description="Year released")
    schema_version: Optional[str] = Field("1.0", description="Schema version for migration support") 