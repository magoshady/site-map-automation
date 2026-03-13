# PV Site Plan Stamper — Implementation Guide

## What this project does

Takes an existing PV (Solar) Site Plan PDF from HubSpot (which already has a satellite image with panel layout) and stamps overlays onto it: a legend (PNG), north arrow, warning banner, and address/system details. Outputs a single-page stamped PDF.

## The script is DONE

`stamp_pv_site_plan.py` is complete and tested. Do NOT modify it unless asked.

It accepts CLI args or a JSON config:
```bash
python3 stamp_pv_site_plan.py --config config.json
```

JSON config format:
```json
{
  "input_pdf": "/tmp/input.pdf",
  "address": "1 Yeramba Avenue, Caringbah South NSW 2229",
  "system_size_kwdc": "7.99",
  "max_dc_voltage": "600",
  "install_date": "11th March 2026",
  "output_pdf": "/tmp/stamped_output.pdf",
  "company_name": "SGI Energy",
  "page_index": 0,
  "legend_image": "/opt/pv-site-plan/assets/legend.png"
}
```

Dependencies: `reportlab`, `Pillow`, `pypdf`

## What needs to be built: n8n workflow

The n8n instance is at n8n.nuevaenergy.com.au (DigitalOcean, Docker, Caddy).

### Workflow steps:

1. **Trigger**: HubSpot deal stage change (deal moves to contracted/won stage)
2. **Get deal properties**: HTTP Request to HubSpot API
   - `GET https://api.hubapi.com/crm/v3/objects/deals/{dealId}?properties=address,system_size_kwdc,max_dc_voltage,install_date`
   - Auth: Bearer token (HubSpot private app)
3. **Download existing site plan PDF**: From HubSpot deal attachments
   - List engagements: `GET https://api.hubapi.com/engagements/v1/engagements/associated/DEAL/{dealId}/paged`
   - Find the attachment with "Site_Plan" or "PV" in filename
   - Download via signed URL: `GET https://api.hubapi.com/filemanager/api/v2/files/{fileId}/signed-url`
4. **Write to disk**: Code node — write PDF binary to `/tmp/input.pdf`, write config JSON to `/tmp/pv_config.json`
5. **Execute script**: Execute Command node — `python3 /opt/pv-site-plan/stamp_pv_site_plan.py --config /tmp/pv_config.json`
6. **Read stamped PDF**: Read Binary File — `/tmp/stamped_{dealId}.pdf`
7. **Upload back to HubSpot**: 
   - Upload file: `POST https://api.hubapi.com/filemanager/api/v3/files/upload`
   - Attach to deal as note: `POST https://api.hubapi.com/engagements/v1/engagements`

### HubSpot deal properties needed:
- `address` (text)
- `system_size_kwdc` (number)  
- `max_dc_voltage` (number)
- `install_date` (text or date)

Adjust internal property names to match whatever already exists in the CRM.

## Server deployment

```bash
sudo mkdir -p /opt/pv-site-plan/assets
sudo cp stamp_pv_site_plan.py /opt/pv-site-plan/
sudo cp assets/legend.png /opt/pv-site-plan/assets/
pip install reportlab Pillow pypdf
```
