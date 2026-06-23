import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// Layout & Guards
import AppLayout from './components/layout/AppLayout';
import PrivateRoute from './components/common/PrivateRoute';
import RoleRoute from './components/common/RoleRoute';

// Pages
import Login from './pages/auth/Login';
import Dashboard from './pages/dashboard/Dashboard';
import UserManagement from './pages/users/UserManagement';
import Employees from './pages/employees/Employees';
import EmployeeDashboard from './pages/employees/EmployeeDashboard';
import Onboarding from './pages/onboarding/Onboarding';
import SOPManagement from './pages/sop/SOPManagement';
import InventoryDashboard from './pages/inventory/InventoryDashboard';
import Assets from './pages/inventory/Assets';
import AssetDeviceDashboard from './pages/inventory/AssetDeviceDashboard';
import InventoryConfig from './pages/inventory/InventoryConfig';
import AssetAllocation from './pages/allocation/AssetAllocation';
import Tickets from './pages/tickets/Tickets';
import Integrations from './pages/integrations/Integrations';
import Organisations from './pages/organisations/Organisations';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<Login />} />

        {/* Authenticated — wrapped in AppLayout */}
        <Route
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          {/* Default redirect */}
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* Dashboard – all authenticated roles */}
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Tickets – all authenticated roles */}
          <Route path="/tickets" element={<Tickets />} />

          {/* Employees – super_admin, hr, it_specialist */}
          <Route
            path="/employees"
            element={
              <RoleRoute roles={['super_admin', 'hr', 'it_specialist']}>
                <Employees />
              </RoleRoute>
            }
          />
          <Route
            path="/employees/:employeeId"
            element={
              <RoleRoute roles={['super_admin', 'hr', 'it_specialist']}>
                <EmployeeDashboard />
              </RoleRoute>
            }
          />

          {/* Onboarding – super_admin, hr, it_specialist */}
          <Route
            path="/onboarding"
            element={
              <RoleRoute roles={['super_admin', 'hr', 'it_specialist']}>
                <Onboarding />
              </RoleRoute>
            }
          />

          {/* SOP – super_admin, it_specialist */}
          <Route
            path="/sop"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <SOPManagement />
              </RoleRoute>
            }
          />

          {/* Inventory Dashboard – super_admin, it_specialist */}
          <Route
            path="/inventory"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <InventoryDashboard />
              </RoleRoute>
            }
          />

          {/* Assets – super_admin, it_specialist */}
          <Route
            path="/inventory/assets"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <Assets />
              </RoleRoute>
            }
          />

          {/* Inventory Config – super_admin, it_specialist */}
          {/* Asset Device Dashboard */}
          <Route
            path="/inventory/assets/:assetId"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <AssetDeviceDashboard />
              </RoleRoute>
            }
          />

          {/* Inventory Config */}
          <Route
            path="/inventory/config"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <InventoryConfig />
              </RoleRoute>
            }
          />

          {/* Allocation – super_admin, it_specialist */}
          <Route
            path="/allocation"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <AssetAllocation />
              </RoleRoute>
            }
          />

          {/* User Management – super_admin only */}
          <Route
            path="/users"
            element={
              <RoleRoute roles={['super_admin']}>
                <UserManagement />
              </RoleRoute>
            }
          />

          {/* Organisations - super_admin only */}
          <Route
            path="/organisations"
            element={
              <RoleRoute roles={['super_admin']}>
                <Organisations />
              </RoleRoute>
            }
          />

          {/* Integrations - super_admin, it_specialist */}
          <Route
            path="/integrations"
            element={
              <RoleRoute roles={['super_admin', 'it_specialist']}>
                <Integrations />
              </RoleRoute>
            }
          />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
