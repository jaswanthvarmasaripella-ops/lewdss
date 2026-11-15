"""
Standard Operating Procedure (SOP) Guidance Module
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Provides:
- NDMA/DDMA-aligned practical disaster preparedness measures.
- Actionable community, transport, and administrative guidance by RLSI susceptibility tier.
- Strict institutional non-alerting disclaimer (all emergency orders are governed by local civil administration).

Follows AGENTS.md: Authentic engineering, practical disaster management, viva-ready clarity.
"""

from typing import Dict, Any, List

INSTITUTIONAL_DISCLAIMER = (
    "LEWDSS is an academic decision-support prototype. It does NOT have legal authority to issue "
    "evacuation orders or official warning bulletins. All emergency advisories, road closures, "
    "and evacuations are governed strictly by the District Disaster Management Authority (DDMA), "
    "State Disaster Management Authority (SDMA), and the National Disaster Management Authority (NDMA)."
)

SOP_GUIDANCE: Dict[str, Dict[str, Any]] = {
    "LOW": {
        "tier_name": "Low Relative Susceptibility",
        "badge_color": "green",
        "administrative_status": "Normal Seasonal Monitoring",
        "community_actions": [
            "Maintain routine clearance of roadside ditches, culverts, and domestic rainwater drains.",
            "Inspect boundary retaining walls and terraces for pre-existing tension cracks or soil settling.",
            "Report uncharacteristic water ponding or muddy seepage near residential slopes to local Gram Panchayat officials.",
        ],
        "infrastructure_actions": [
            "Normal traffic operations on ghat and mountain roads.",
            "Routine maintenance inspection of slope reinforcement netting and culverts along key highway corridors.",
        ],
        "emergency_desk_checklist": [
            "Standard monitoring of daily Indian Meteorological Department (IMD) district rainfall bulletins.",
            "Maintain baseline inventory of emergency machinery (excavators, backhoes) at taluk headquarters.",
        ],
    },
    "ELEVATED": {
        "tier_name": "Elevated Relative Susceptibility",
        "badge_color": "amber",
        "administrative_status": "Heightened Vigilance & Advisory Mode",
        "community_actions": [
            "Advise residents living near steep, modified, or previously failed slopes to monitor for fresh ground cracks.",
            "Avoid non-essential nighttime travel along steep mountain roads during periods of continuous rainfall.",
            "Ensure household emergency battery packs, flashlights, and mobile communications remain charged.",
            "Identify nearest designated community relief shelters and primary evacuation walking routes.",
        ],
        "infrastructure_actions": [
            "Deploy road maintenance inspection teams along vulnerable highway stretches with known chronic slide history.",
            "Verify that earthmoving equipment and operators are on stand-by at taluk public works depots.",
            "Install temporary cautionary signage along identified steep cuttings with loose boulders or saturated soils.",
        ],
        "emergency_desk_checklist": [
            "Track 24-hour and 72-hour rainfall accumulation against regional historical flash flood/landslide averages.",
            "Establish active communication check-ins between District Emergency Operations Centre (DEOC) and taluk tehsildars.",
            "Verify satellite phone communication readiness for remote hillside villages vulnerable to road cutoffs.",
        ],
    },
    "HIGH": {
        "tier_name": "High Relative Susceptibility",
        "badge_color": "red",
        "administrative_status": "Preparedness Advisory & Resource Standby",
        "community_actions": [
            "Review family emergency communication plan and keep essential medications, identity documents, and emergency bags accessible.",
            "Heed official notifications from District Collector / DDMA regarding potential localized precautionary relocation.",
            "Immediately report rapid water color changes (sudden mud surges in clear mountain streams) or ground rumbling to local authorities.",
            "Stay clear of river channels and steep ravines susceptible to debris flows during intense cloudbursts.",
        ],
        "infrastructure_actions": [
            "Position heavy earthmoving equipment and debris clearance squads at strategic junctions along critical arterial highways.",
            "Coordinate with Traffic Police for possible restricted/regulated heavy-vehicle movement on vulnerable ghat routes.",
            "Inspect bridge abutments and mountain stream crossings for debris damming or backwater accumulation.",
        ],
        "emergency_desk_checklist": [
            "Activate emergency relief centers / relief camps in secure, low-hazard taluk school buildings or auditoriums.",
            "Coordinate inter-agency stand-by status with National Disaster Response Force (NDRF) / State Disaster Response Force (SDRF).",
            "Prepare official advisory bulletins for dissemination through DDMA authorized public broadcast channels.",
        ],
    },
}


def get_sop_guidance(category_code: str) -> Dict[str, Any]:
    """
    Retrieve practical SOP guidance by susceptibility tier.

    Parameters
    ----------
    category_code : str
        'LOW', 'ELEVATED', or 'HIGH'.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing actions, administrative status, and disclaimers.
    """
    code = category_code.upper()
    guidance = SOP_GUIDANCE.get(code, SOP_GUIDANCE["LOW"])
    return {
        "category_code": code,
        "tier_name": guidance["tier_name"],
        "badge_color": guidance["badge_color"],
        "administrative_status": guidance["administrative_status"],
        "community_actions": list(guidance["community_actions"]),
        "infrastructure_actions": list(guidance["infrastructure_actions"]),
        "emergency_desk_checklist": list(guidance["emergency_desk_checklist"]),
        "institutional_disclaimer": INSTITUTIONAL_DISCLAIMER,
    }
