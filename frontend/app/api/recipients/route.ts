import { NextResponse } from "next/server";

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.NEXT_PUBLIC_SUPABASE_KEY || "";

export async function GET() {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return NextResponse.json({ recipients: [] });
  }
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/recipients?is_active=eq.true&select=email,country`,
      {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return NextResponse.json({ recipients: [] });
    }

    const rows: { email: string; country: string }[] = await res.json();

    // Group by country
    const byCountry: Record<string, string[]> = {};
    for (const row of rows) {
      let emails: string[] = [];
      const raw = row.email || "";
      if (typeof raw === "string" && raw.startsWith("[")) {
        try {
          emails = JSON.parse(raw);
        } catch {
          emails = [raw];
        }
      } else {
        emails = [raw];
      }
      const country = row.country || "ALL";
      if (!byCountry[country]) byCountry[country] = [];
      for (const e of emails) {
        const trimmed = e.trim();
        if (trimmed && trimmed.includes("@")) {
          byCountry[country].push(trimmed);
        }
      }
    }

    const recipients = Object.entries(byCountry).map(([country, to]) => ({
      country,
      to,
      cc: [],
    }));

    return NextResponse.json({ recipients });
  } catch {
    return NextResponse.json({ recipients: [] });
  }
}
