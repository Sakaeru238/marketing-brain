import json

from core.loaders.run_loader import RunLoader
from core.loaders.campaign_loader import CampaignLoader
from core.loaders.creative_control_loader import CreativeControlLoader
from core.loaders.creative_style_loader import CreativeStyleLoader

CONTROL_PANEL_FILE = "marketing_brain_control_panel.xlsx"
RUN_ID = "AODAI_01"


run_loader = RunLoader(CONTROL_PANEL_FILE)
campaign_loader = CampaignLoader(CONTROL_PANEL_FILE)
creative_control_loader = CreativeControlLoader(CONTROL_PANEL_FILE)
creative_style_loader = CreativeStyleLoader(CONTROL_PANEL_FILE)


run = run_loader.load_run(RUN_ID)
campaign = campaign_loader.load_campaign(run["campaign_id"])
creative_control = creative_control_loader.load_creative_control(RUN_ID)
style_library = creative_style_loader.load_style_library()


print("\n====== RUN ======\n")
print(json.dumps(run, ensure_ascii=False, indent=2))

print("\n====== CAMPAIGN ======\n")
print(json.dumps(campaign, ensure_ascii=False, indent=2))

print("\n====== CREATIVE CONTROL ======\n")
print(json.dumps(creative_control, ensure_ascii=False, indent=2))

print("\n====== STYLE LIBRARY IDS ======\n")
print(json.dumps(list(style_library.keys()), ensure_ascii=False, indent=2))
