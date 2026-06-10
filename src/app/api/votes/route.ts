import { NextResponse } from "next/server";
import { getVoteCounts } from "@/lib/votes";

export const revalidate = 60;

export async function GET() {
  const counts = await getVoteCounts();
  return NextResponse.json({ counts });
}
