from typing import Dict, Any, Optional
from django.conf import settings
import google.generativeai as genai
from .models import Contract
import json

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

class GeminiHelper:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def _sanitize_profile(self, profile: Any) -> Dict[str, Any]:
        """ Ensure profile is a dict and not a list """
        if isinstance(profile, list):
            return profile[0] if profile else {}
        return profile or {}

    def _build_prompt(self, contract_data, profile_owner, profile_client, equipment_info) -> str:
        """
        Build a readable prompt from the provided dictionaries for Gemini.
        """
        profile_owner = self._sanitize_profile(profile_owner)
        profile_client = self._sanitize_profile(profile_client)

        prompt = f"""
Generate a professional HTML equipment rental contract based on the following data:

📄 Contract Details:
- Owner Name: {contract_data.get("owner_name")}
- Client Name: {contract_data.get("client_name")}
- Start Date: {contract_data.get("start_date")}
- End Date: {contract_data.get("end_date")}
- Total Value: {contract_data.get("total_value")} TND

👤 Owner Profile:
- Full Name: {profile_owner.get("first_name", "")} {profile_owner.get("last_name", "")}
- Phone: {profile_owner.get("phone", "")}
- Address: {profile_owner.get("address", {}).get("street", "")}, {profile_owner.get("address", {}).get("city", "")}, {profile_owner.get("address", {}).get("state", "")}, {profile_owner.get("address", {}).get("postal_code", "")}, {profile_owner.get("address", {}).get("country", "")}

👤 Client Profile:
- Full Name: {profile_client.get("first_name", "")} {profile_client.get("last_name", "")}
- Phone: {profile_client.get("phone", "")}
- Address: {profile_client.get("address", {}).get("street", "")}, {profile_client.get("address", {}).get("city", "")}, {profile_client.get("address", {}).get("state", "")}, {profile_client.get("address", {}).get("postal_code", "")}, {profile_client.get("address", {}).get("country", "")}

🛠️ Equipment Information:
- Name: {equipment_info.get("stuffname", "")}
- Brand: {equipment_info.get("brand", "")}
- Location: {equipment_info.get("location", "")}
- Price per day: {equipment_info.get("price_per_day", "")} TND
- Condition: {equipment_info.get("state", "")}
- Rental Location: {equipment_info.get("rental_location", "")}
- Description: {equipment_info.get("short_description", "")}

📄 Detailed Description:
{equipment_info.get("detailed_description", "")}

Please return a well-structured HTML contract that includes the parties' names, equipment details, rental terms, and a signature section for both the owner and the client.
"""
        return prompt

    def generate_contract_html(
        self,
        contract_data: Dict[str, Any],
        profile_owner: Optional[Dict[str, Any]] = None,
        profile_client: Optional[Dict[str, Any]] = None,
        equipment_info: Optional[Any] = None,
    ) -> str:
        """
        Pass raw data to Gemini model to generate the contract HTML.
        """
        prompt_text = self._build_prompt(contract_data, profile_owner, profile_client, equipment_info)

        # Gemini expects { "parts": [ { "text": "..."} ] }
        response = self.model.generate_content({
            "parts": [
                {"text": prompt_text}
            ]
        })

        return response.text  # Assuming Gemini returns the contract HTML here

    def create_draft_contract(
        self,
        contract_data: dict,
        profile_owner: Optional[Dict[str, Any]] = None,
        profile_client: Optional[Dict[str, Any]] = None,
        equipment_info: Optional[Any] = None,
    ) -> Contract:
        # Ask Gemini to generate the HTML from raw data
        contract_html = self.generate_contract_html(contract_data, profile_owner, profile_client, equipment_info)

        contract = Contract.objects.create(
            owner_name=contract_data["owner_name"],
            client_name=contract_data["client_name"],
            equipment=contract_data["equipment"],
            contract_text=contract_html,
            status='draft',
            total_value=contract_data.get("total_value") or 0,
            start_date=contract_data.get("start_date"),
            end_date=contract_data.get("end_date")
        )
        return contract
