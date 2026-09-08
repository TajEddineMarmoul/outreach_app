import { auth } from "@clerk/nextjs/server";
import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { NextResponse } from "next/server";

const MAX_CSV_FILE_BYTES = 100 * 1024 * 1024;
const PRIVATE_IMPORT_PATH = /^campaign-imports\/[^/]+\/[^/]+\.csv$/i;

export const runtime = "nodejs";

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json()) as HandleUploadBody;
  try {
    const response = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        const { userId } = await auth();
        if (!userId) throw new Error("Authentication required");
        if (!PRIVATE_IMPORT_PATH.test(pathname)) throw new Error("Invalid import upload path");
        return {
          allowedContentTypes: ["text/csv"],
          maximumSizeInBytes: MAX_CSV_FILE_BYTES,
          addRandomSuffix: true,
        };
      },
    });
    return NextResponse.json(response);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Could not prepare the CSV upload" },
      { status: 400 },
    );
  }
}
