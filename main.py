import os
from datetime import datetime, timezone
from certifi import contents
from google import genai
from google.genai import types
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def get_upcoming_events(max_results: int = 5) -> dict:
    """Mengambil daftar agenda atau acara terdekat dari Google Calendar pengguna

    mulai dari waktu sekarang.

    Args:
        max_results: Jumlah maksimal agenda yang ingin diambil (default: 5).
    """
    service = get_calendar_service()

    # Waktu sekarang dalam format UTC ISO string
    now = datetime.now(timezone.utc).isoformat()

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    items = events_result.get("items", [])
    if not items:
        return {"events": [], "message": "Tidak ada jadwal mendatang."}

    parsed_events = []
    for event in items:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        parsed_events.append({
            "id": event.get("id"),
            "summary": event.get("summary", "Tanpa Judul"),
            "start": start,
            "end": end,
            "description": event.get("description", ""),
        })

    return {"events": parsed_events}

def create_calendar_event(
    summary: str, start_time: str, end_time: str, description: str = ""
) -> dict:
    """Membuat agenda baru di Google Calendar.

    Args:
        summary: Judul atau nama acara/meeting.
        start_time: Waktu mulai dalam format ISO 8601 (contoh:
          '2026-09-10T14:00:00+07:00').
        end_time: Waktu selesai dalam format ISO 8601 (contoh:
          '2026-09-10T15:00:00+07:00').
        description: Deskripsi tambahan tentang agenda.
    """
    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    created_event = (
        service.events().insert(calendarId="primary", body=event_body).execute()
    )
    return {
        "status": "success",
        "event_id": created_event.get("id"),
        "html_link": created_event.get("htmlLink"),
    }


# Mapping fungsi agar mudah dieksekusi secara dinamis
available_tools = {
    "get_upcoming_events": get_upcoming_events,
    "create_calendar_event": create_calendar_event,
}


client = genai.Client()
user_prompt = "sebutkan jadwal terdekat saya lalu Jadwalkan tes gemini 2 3.1 besok tanggal 12 September 2026 jam 10 pagi sampai jam 11 siang WIB."


response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=user_prompt,
    config=types.GenerateContentConfig(
        tools=[get_upcoming_events, create_calendar_event],
        temperature=0,
    ),
)

while response.function_calls:
    contents.append(response.candidates[0].content)
    tool_responses = []

    for call in response.function_calls:
        fn_name = call.name
        fn_args = dict(call.args)
        print(f"-> Memanggil Tool: {fn_name} dengan argumen {fn_args}")

        if fn_name in available_tools:
            tool_output = available_tools[fn_name](**fn_args)
        else:
            tool_output = {"error": f"Fungsi {fn_name} tidak ditemukan"}

        tool_responses.append(
            types.Part.from_function_response(
                name=fn_name,
                response={"result": tool_output},
            )
        )
    
    contents.append(types.Content(role="user", parts=tool_responses))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[get_upcoming_events, create_calendar_event],
            temperature=0,
        ),
    )

print("\nJawaban Gemini:")
print(response.text)