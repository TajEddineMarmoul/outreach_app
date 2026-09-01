import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-7 px-5 py-10">
      <Link href="/" className="text-sm text-blue-600 underline-offset-4 hover:underline">← Back to Outreach home</Link>
      <SignIn />
    </div>
  );
}
