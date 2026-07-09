export function isAdminUser(user: unknown): boolean {
  const meta = (user as Record<string, unknown> | undefined)?.publicMetadata as Record<string, unknown> | undefined;
  return meta?.role === "admin";
}
