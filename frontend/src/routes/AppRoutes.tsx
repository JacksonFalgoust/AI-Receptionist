import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ActivityPage } from '@/pages/ActivityPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { BillingPage } from '@/pages/BillingPage'
import { ConfigurationPage } from '@/pages/ConfigurationPage'
import { ConversationDetailPage } from '@/pages/ConversationDetailPage'
import { ConversationsPage } from '@/pages/ConversationsPage'
import { FeaturesPage } from '@/pages/FeaturesPage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { HelpPage } from '@/pages/HelpPage'
import { IntegrationsPage } from '@/pages/IntegrationsPage'
import { InvitePage } from '@/pages/InvitePage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OverviewPage } from '@/pages/OverviewPage'
import { RoutingPage } from '@/pages/RoutingPage'
import { SecurityPage } from '@/pages/SecurityPage'
import { TestPage } from '@/pages/TestPage'
import { UsersPage } from '@/pages/UsersPage'
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
          <Route path={paths.test} element={<TestPage />} />
          <Route path={paths.help} element={<HelpPage />} />

          <Route element={<ProtectedRoute permission="view:conversations" />}>
            <Route path={paths.conversations} element={<ConversationsPage />} />
            <Route path={paths.conversation()} element={<ConversationDetailPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="view:activity" />}>
            <Route path={paths.activity} element={<ActivityPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="view:analytics" />}>
            <Route path={paths.analytics} element={<AnalyticsPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:knowledge" />}>
            <Route path={paths.knowledge} element={<KnowledgePage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:configuration" />}>
            <Route path={paths.configuration} element={<ConfigurationPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:features" />}>
            <Route path={paths.features} element={<FeaturesPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:workflows" />}>
            <Route path={paths.workflows} element={<WorkflowsPage />} />
            <Route path={paths.workflow()} element={<WorkflowDetailPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:integrations" />}>
            <Route path={paths.integrations} element={<IntegrationsPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:routing" />}>
            <Route path={paths.routing} element={<RoutingPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:users" />}>
            <Route path={paths.users} element={<UsersPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="view:security" />}>
            <Route path={paths.security} element={<SecurityPage />} />
          </Route>

          <Route element={<ProtectedRoute permission="manage:billing" />}>
            <Route path={paths.billing} element={<BillingPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to={paths.overview} replace />} />
    </Routes>
  )
}
