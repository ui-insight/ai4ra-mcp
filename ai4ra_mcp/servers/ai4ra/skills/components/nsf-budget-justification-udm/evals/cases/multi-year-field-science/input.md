## Structured budget

```json
{
  "project_title": "Scaling Leaf-to-Canopy Optical Traits Across a Mediterranean-Climate Gradient",
  "project_summary": "Three-year field and modeling study linking in-situ leaf optical measurements to canopy-scale remote-sensing observations across a Mediterranean-climate aridity gradient in coastal California. The project combines field spectroscopy campaigns, soil biogeochemistry analyses at a collaborating institution, and an undergraduate summer research program.",
  "project_years": 3,
  "personnel": [
    {
      "name": "Dr. Terra López",
      "role": "Principal Investigator",
      "senior": true,
      "effort": { "unit": "summer_months", "value": 1 },
      "base_salary": 175000,
      "escalation_percent": 3,
      "funding_source": "One summer month per year."
    },
    {
      "name": "Dr. Sam Ng",
      "role": "Co-Principal Investigator",
      "senior": true,
      "effort": { "unit": "summer_months", "value": 1 },
      "base_salary": 140000,
      "escalation_percent": 3,
      "funding_source": "One summer month per year."
    },
    {
      "name": "Postdoctoral Researcher (TBN)",
      "role": "Postdoctoral Researcher",
      "senior": false,
      "effort": { "unit": "percent", "value": 100 },
      "base_salary": 65000,
      "escalation_percent": 3,
      "funding_source": "Calendar-year 100% appointment."
    },
    {
      "name": "Graduate Research Assistant 1",
      "role": "Graduate Student",
      "senior": false,
      "effort": { "unit": "percent", "value": 50 },
      "base_salary": 32000,
      "escalation_percent": 3,
      "funding_source": "50% academic year and 100% summer appointment; stipend per institutional GRA schedule."
    },
    {
      "name": "Graduate Research Assistant 2",
      "role": "Graduate Student",
      "senior": false,
      "effort": { "unit": "percent", "value": 50 },
      "base_salary": 32000,
      "escalation_percent": 3,
      "funding_source": "50% academic year and 100% summer appointment; stipend per institutional GRA schedule."
    },
    {
      "name": "Undergraduate Research Assistant (TBN)",
      "role": "Undergraduate Research Assistant",
      "senior": false,
      "effort": { "unit": "percent", "value": 25 },
      "base_salary": 6000,
      "escalation_percent": 3,
      "funding_source": "Summer hourly appointment, ~400 hours per year at the institution's undergraduate research rate."
    }
  ],
  "budget_summary": {
    "categories": {
      "A": [35000, 36050, 37130],
      "B": [111000, 114330, 117770],
      "C": [37500, 38650, 39810],
      "D": [28500, 0, 0],
      "E": [8500, 8500, 8500],
      "F": [0, 45000, 45000],
      "G": [113000, 116360, 121730]
    }
  },
  "indirect_cost": {
    "rate_percent": 52,
    "base_description": "Modified Total Direct Costs (MTDC) excluding equipment, participant support costs, and the portion of each subaward in excess of $25,000.",
    "off_campus_rate_percent": 26,
    "rate_agreement_citation": "DHHS-negotiated F&A rate agreement, current through 2028.",
    "notes": "Rate steps up from 52% (Years 1 and 2) to 54.5% (Year 3) per the current rate agreement."
  },
  "equipment_items": [
    {
      "name": "Field spectroradiometer (visible to shortwave-infrared, continuous)",
      "year": 1,
      "amount": 28500,
      "justification_hint": "Required for in-situ leaf- and canopy-scale reflectance measurements at the California study site. No suitable instrument is available through the institution's shared spectroscopy facility, and loaner windows from nearby field stations do not cover the campaign schedule."
    }
  ],
  "travel_detail": {
    "domestic_purposes": [
      "PI and one graduate student to attend the annual American Geophysical Union meeting each project year to present project results.",
      "PI, co-PI, postdoctoral researcher, and two graduate students to travel to the California study site for two ten-day field campaigns per year."
    ],
    "international_purposes": []
  },
  "participant_support_detail": {
    "program_purpose": "Two-week summer research experience for six undergraduate students at the prime institution, in Years 2 and 3, mentored by the PI, co-PI, and postdoctoral researcher.",
    "line_items": [
      { "category": "stipend",     "count": 6, "amount_per": 3000, "description": "Stipend per participant for the two-week program." },
      { "category": "travel",      "count": 6, "amount_per": 500,  "description": "Round-trip travel to the host institution." },
      { "category": "subsistence", "count": 6, "amount_per": 3000, "description": "On-campus housing and meals during the program." },
      { "category": "fee",         "count": 6, "amount_per": 1000, "description": "Program registration and materials fee." }
    ]
  },
  "subawards": [
    {
      "institution": "State University of X",
      "pi_name": "Dr. Jamie Park",
      "scope": "Soil biogeochemistry analyses — trace-gas flux measurements and isotope-ratio mass spectrometry on soil cores collected at the California study site. Performed at the subrecipient's established biogeochemistry laboratory, which operates instrumentation not available at the prime institution.",
      "amount_by_year": [95000, 98000, 101000]
    }
  ],
  "other_direct_costs_detail": {
    "materials_and_supplies": "Expendable field supplies (sample bags, vials, tubing, reagents), calibration targets for the spectroradiometer, and consumables for GPS and data-logging equipment, budgeted at approximately $6,000 per year.",
    "publication_costs": "Page charges and open-access fees for two peer-reviewed manuscripts projected for submission in Year 3.",
    "consultant_services": null,
    "computer_services": null,
    "other": "Tuition remission for the two graduate research assistants, budgeted per institutional rates and accounted under NSF Other Direct Costs per institutional budgeting policy."
  }
}
```
