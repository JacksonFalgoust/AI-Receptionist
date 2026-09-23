import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ConfigurationPage } from '@/pages/ConfigurationPage'
import { ConversationDetailPage } from '@/pages/ConversationDetailPage'
import { ConversationsPage } from '@/pages/ConversationsPage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { HelpPage } from '@/pages/HelpPage'
import { InvitePage } from '@/pages/InvitePage'
import { KnowledgeEditorPage } from '@/pages/KnowledgeEditorPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OverviewPage } from '@/pages/OverviewPage'
import { TestPage } from '@/pages/TestPage'
import { WorkflowDetailPage } from '@/pages/WorkflowDetailPage'
import { WorkflowsPage } from '@/pages/WorkflowsPage'

import { paths } from './paths'
import { ProtectedRoute } from './ProtectedRoute'

export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path={paths.login} element={<LoginPage />} />
      <Route path={paths.forgotPassword} element={<ForgotPasswordPage />} />
      <Route path={paths.invite()} element={<InvitePage />} />

      {/* Authenticated */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path={paths.overview} element={<OverviewPage />} />
          {/* US-13.1 / PRD §40. use:test already existed in lib/permissions.ts
              (owner, administrator, manager) but nothing enforced it until
              now. IMPORTANT: this is a navigation guard only — E6 must
              enforce the same rule server-side before a real backend ships. */}
          <Route element={<ProtectedRoute permission="use:test" />}>
            <Route path={paths.test} element={<TestPage />} />
          </Route>
          <Route path={paths.help} element={<HelpPage />} />

          <Route element={<ProtectedRoute permission="view:conversations" />}>
            <Route path={paths.conversations} element={<ConversationsPage />} />
            <Route path={paths.conversation()} element={<ConversationDetailPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:knowledge" />}>
            <Route path={paths.knowledge} element={<KnowledgePage />} />
            {/* Static `new` outranks `:id`, so the add route is never read as
                an item whose id is the word "new". */}
            <Route path={paths.knowledgeNew} element={<KnowledgeEditorPage />} />
            <Route path={paths.knowledgeItem()} element={<KnowledgeEditorPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:configuration" />}>
            <Route path={paths.configuration} element={<ConfigurationPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:workflows" />}>
            <Route path={paths.workflows} element={<WorkflowsPage />} />
            <Route path={paths.workflow()} element={<WorkflowDetailPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to={paths.overview} replace />} />
    </Routes>
  )
}
