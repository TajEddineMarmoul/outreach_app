export const TEMPLATE_VARIABLE_PATTERN = /\{\{\s*([^{}]+?)\s*\}\}/g;

export function templateVariableName(variable: string): string {
  return variable.trim();
}

export function extractTemplateVariables(template: string): string[] {
  return [...template.matchAll(TEMPLATE_VARIABLE_PATTERN)].map((match) =>
    templateVariableName(match[1])
  );
}
