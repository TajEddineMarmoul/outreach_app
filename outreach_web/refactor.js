const fs = require('fs');
const path = 'c:/Users/tajdi/Documents/GitHub/outreach_app/outreach_web/src/app/campaigns/[id]/page.tsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace(
  'import RichTextEditor from "@/components/RichTextEditor";',
  'import RichTextEditor from "@/components/RichTextEditor";\nimport ScheduleDialog from "@/components/campaigns/dialogs/ScheduleDialog";\nimport SenderSelectionDialog from "@/components/campaigns/dialogs/SenderSelectionDialog";\nimport PreviewDialog from "@/components/campaigns/dialogs/PreviewDialog";\nimport AttachmentDialog from "@/components/campaigns/dialogs/AttachmentDialog";'
);

content = content.replace(/<SendCampaignDialog/g, '<ScheduleDialog');
content = content.replace(/<\/SendCampaignDialog>/g, '</ScheduleDialog>');
content = content.replace(/<SenderDialog/g, '<SenderSelectionDialog');
content = content.replace(/<\/SenderDialog>/g, '</SenderSelectionDialog>');

const start1 = content.indexOf('// 1. Send Campaign Dialog');
const end1 = content.indexOf('// 3. Select Recipients Dialog');
if (start1 !== -1 && end1 !== -1) {
  content = content.substring(0, start1) + content.substring(end1);
}

const start2 = content.indexOf('// 4. Preview Dialog');
const end2 = content.indexOf('// 6. Template Dialog');
if (start2 !== -1 && end2 !== -1) {
  content = content.substring(0, start2) + content.substring(end2);
}

fs.writeFileSync(path, content);
console.log('Refactoring complete');
