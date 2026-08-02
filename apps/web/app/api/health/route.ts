export async function GET() {
  return Response.json(
    { status: "ok", service: "ug-utag-web" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
