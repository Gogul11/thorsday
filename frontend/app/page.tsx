import { redirect } from "next/navigation";

/**
 * Root entry point — immediately redirects to the chat page.
 * All actual page content lives under pages/chat/index.tsx.
 */
export default function Home() {
  redirect("/chat");
}
