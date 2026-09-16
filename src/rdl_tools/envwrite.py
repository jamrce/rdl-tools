"""Derive `.env` values from parsed RDF plus whatever the user was asked, and write `.env`.

`.env` holds identity, URL and presentation keys only; everything the site shows about the
ontology itself comes from RDF at render time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from rdflib import Graph
from rdflib.namespace import Namespace
from rdflib.term import Node

from .spec import write_generated

VANN = Namespace("http://purl.org/vocab/vann/")

SLUG_RE = re.compile(r"[^a-z0-9]+")
VERSION_SEGMENT_RE = re.compile(r"^v\d+$")

# Presentation flags a new module gets, with the template's defaults.
PRESENTATION_DEFAULTS = {
    "BRAND_SUBTITLE": "Reference Data Library",
    "BRAND_MARK": "",
    "REPO_URL": "",
    "ACCENT_COLOR": "",
    "DEFAULT_COLOR_MODE": "light",
    "TERM_LABEL_SOURCE": "localName",
    "EXTERNAL_LINK_POLICY": "resolve",
    "RELEASE_DATE_SOURCE": "dcterms:modified",
    "DOWNLOAD_FORMATS": "ttl,rdf,jsonld,nt",
    "SHOW_FOOTER": "false",
}

ENV_KEY_ORDER = [
    "MODULE_SLUG",
    "MODULE_NAMESPACE",
    "REPO_OWNER",
    "PAGES_ORIGIN",
    "WEBSITE_BASE_URL",
    "W3ID_AUTHORITY",
    *PRESENTATION_DEFAULTS,
]


@dataclass
class SlugResult:
    slug: str
    source: str  # "namespace" | "title" | "folder"
    folder_mismatch: bool


def namespace_path_segments(namespace_uri: str) -> list[str]:
    return [s for s in urlparse(namespace_uri).path.split("/") if s]


def slugify_title(title: str) -> str:
    return SLUG_RE.sub("-", title.strip().lower()).strip("-")


def derive_slug(namespace_uri: str, title: str, folder_name: str) -> SlugResult:
    """MODULE_SLUG: the namespace segment before the version segment, else a slugified
    `dcterms:title`, else the folder name.

    The namespace segment leads because a title that does not match the repo name slugs wrong.
    """
    segments = namespace_path_segments(namespace_uri)
    for index, segment in enumerate(segments):
        if VERSION_SEGMENT_RE.match(segment) and index > 0:
            slug = segments[index - 1]
            return SlugResult(slug, "namespace", slug != folder_name)

    if title:
        slug = slugify_title(title)
        if slug:
            return SlugResult(slug, "title", slug != folder_name)

    return SlugResult(folder_name, "folder", False)


def w3id_authority_default(namespace_uri: str) -> str | None:
    """The namespace's own authority segment, only when the namespace is itself a w3id.org IRI —
    never guessed from the repo owner, which would mint pins under the wrong authority silently."""
    parsed = urlparse(namespace_uri)
    if parsed.netloc != "w3id.org":
        return None
    segments = [s for s in parsed.path.split("/") if s]
    return segments[0] if segments else None


def preferred_namespace_uri(graph: Graph, ontology_iri: Node) -> str | None:
    value = next(graph.objects(ontology_iri, VANN.preferredNamespaceUri), None)
    return str(value) if value is not None else None


def escape_env_value(value: str) -> str:
    """A dotenv-safe scalar: RDF literals carry `#`, quotes and newlines, which all break a parse."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r'[\n#"]', normalized) or normalized != normalized.strip():
        escaped = normalized.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return normalized


def render_env(values: dict[str, str]) -> str:
    lines = [f"{key}={escape_env_value(values[key])}" for key in ENV_KEY_ORDER if key in values]
    return "\n".join(lines) + "\n"


def build_env(
    *,
    module_namespace: str,
    slug: str,
    repo_owner: str,
    w3id_authority: str,
    website_base_url: str | None = None,
    pages_origin: str | None = None,
) -> dict[str, str]:
    """`website_base_url` / `pages_origin` are written only when the module diverges from the
    template's `REPO_OWNER`/`MODULE_SLUG` default — a `{user}.github.io` repo, or a custom domain."""
    values = {
        "MODULE_SLUG": slug,
        "MODULE_NAMESPACE": module_namespace,
        "REPO_OWNER": repo_owner,
        "W3ID_AUTHORITY": w3id_authority,
        **PRESENTATION_DEFAULTS,
    }
    if pages_origin is not None:
        values["PAGES_ORIGIN"] = pages_origin
    if website_base_url is not None:
        values["WEBSITE_BASE_URL"] = website_base_url
    return values


def write_env(module_dir: Path, values: dict[str, str], *, force: bool = False) -> Path:
    env_path = module_dir / ".env"
    if env_path.exists() and not force:
        raise FileExistsError(f"{env_path} already exists (use --force to overwrite)")
    write_generated(env_path, render_env(values))
    return env_path
