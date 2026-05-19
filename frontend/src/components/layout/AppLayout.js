import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Avatar,
  Tooltip,
  Collapse,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PeopleIcon from '@mui/icons-material/People';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import DevicesIcon from '@mui/icons-material/Devices';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import LogoutIcon from '@mui/icons-material/Logout';
import InventoryIcon from '@mui/icons-material/Inventory';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import TuneIcon from '@mui/icons-material/Tune';
import { useAuth } from '../../context/AuthContext';

const DRAWER_OPEN_WIDTH = 260;
const DRAWER_COLLAPSED_WIDTH = 64;

const NAV_SECTIONS = [
  {
    title: '',
    items: [
      {
        label: 'Dashboard',
        icon: <DashboardIcon />,
        path: '/dashboard',
        roles: ['super_admin', 'hr', 'it_specialist', 'employee'],
      },
    ],
  },
  {
    title: 'HR',
    roles: ['super_admin', 'hr', 'it_specialist'],
    items: [
      {
        label: 'Employees',
        icon: <PeopleIcon />,
        path: '/employees',
        roles: ['super_admin', 'hr', 'it_specialist'],
      },
      {
        label: 'New Joiner Onboarding',
        icon: <PersonAddIcon />,
        path: '/onboarding',
        roles: ['super_admin', 'hr', 'it_specialist'],
      },
    ],
  },
  {
    title: 'IT Operations',
    roles: ['super_admin', 'it_specialist'],
    items: [
      {
        label: 'IT Assets',
        icon: <DevicesIcon />,
        path: '/inventory/assets',
        roles: ['super_admin', 'it_specialist'],
      },
      {
        label: 'Inventory Dashboard',
        icon: <InventoryIcon />,
        path: '/inventory',
        roles: ['super_admin', 'it_specialist'],
      },
      {
        label: 'Asset Allocation',
        icon: <SwapHorizIcon />,
        path: '/allocation',
        roles: ['super_admin', 'it_specialist'],
      },
      {
        label: 'SOP Management',
        icon: <MenuBookIcon />,
        path: '/sop',
        roles: ['super_admin', 'it_specialist'],
      },
      {
        label: 'Inventory Config',
        icon: <TuneIcon />,
        path: '/inventory/config',
        roles: ['super_admin', 'it_specialist'],
      },
    ],
  },
  {
    title: 'Support',
    items: [
      {
        label: 'Tickets',
        icon: <ConfirmationNumberIcon />,
        path: '/tickets',
        roles: ['super_admin', 'hr', 'it_specialist', 'employee'],
      },
    ],
  },
  {
    title: 'Admin',
    roles: ['super_admin'],
    items: [
      {
        label: 'User Management',
        icon: <AdminPanelSettingsIcon />,
        path: '/users',
        roles: ['super_admin'],
      },
    ],
  },
];

function SidebarSection({ section, open, currentPath, onNavigate, userRole }) {
  const [expanded, setExpanded] = useState(true);

  // Filter items by role
  const visibleItems = section.items.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  );

  if (visibleItems.length === 0) return null;

  // Check section-level role gate
  if (section.roles && !section.roles.includes(userRole)) return null;

  return (
    <>
      {section.title && open && (
        <ListItem disablePadding sx={{ mt: 1 }}>
          <ListItemButton
            onClick={() => setExpanded(!expanded)}
            sx={{ py: 0.5 }}
          >
            <ListItemText
              primary={section.title}
              primaryTypographyProps={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: 1,
                color: 'text.secondary',
                textTransform: 'uppercase',
              }}
            />
            {expanded ? (
              <ExpandLess fontSize="small" sx={{ color: 'text.secondary' }} />
            ) : (
              <ExpandMore fontSize="small" sx={{ color: 'text.secondary' }} />
            )}
          </ListItemButton>
        </ListItem>
      )}

      <Collapse in={!section.title || !open || expanded} timeout="auto" unmountOnExit={false}>
        {visibleItems.map((item) => {
          const isActive = currentPath === item.path || currentPath.startsWith(item.path + '/');
          return (
            <ListItem key={item.path} disablePadding sx={{ display: 'block' }}>
              <Tooltip title={!open ? item.label : ''} placement="right">
                <ListItemButton
                  onClick={() => onNavigate(item.path)}
                  selected={isActive}
                  sx={{
                    minHeight: 44,
                    justifyContent: open ? 'initial' : 'center',
                    px: 2.5,
                    borderRadius: 1,
                    mx: 1,
                    mb: 0.25,
                    '&.Mui-selected': {
                      backgroundColor: 'primary.main',
                      color: 'white',
                      '&:hover': { backgroundColor: 'primary.dark' },
                      '& .MuiListItemIcon-root': { color: 'white' },
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: open ? 1.5 : 'auto',
                      justifyContent: 'center',
                      color: isActive ? 'white' : 'text.secondary',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  {open && (
                    <ListItemText
                      primary={item.label}
                      slotProps={{ primary: { style: { fontSize: 14, fontWeight: isActive ? 600 : 400 } } }}
                    />
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          );
        })}
      </Collapse>

      {section.title && <Divider sx={{ my: 1, mx: 2 }} />}
    </>
  );
}

function AppLayout() {
  const [open, setOpen] = useState(true);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const drawerWidth = open ? DRAWER_OPEN_WIDTH : DRAWER_COLLAPSED_WIDTH;
  const userRole = user?.role || 'employee';
  const userName = user?.full_name || user?.email || 'User';
  const initials = userName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'grey.50' }}>
      {/* AppBar */}
      <AppBar
        position="fixed"
        elevation={1}
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          width: '100%',
          bgcolor: 'primary.main',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setOpen(!open)}
            sx={{ mr: 1 }}
          >
            {open ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          <Typography variant="h6" fontWeight={700} sx={{ flexGrow: 1, letterSpacing: 0.5 }}>
            IT Support Portal
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar sx={{ bgcolor: 'secondary.main', width: 34, height: 34, fontSize: 14 }}>
              {initials}
            </Avatar>
            <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
              <Typography variant="body2" fontWeight={600} sx={{ lineHeight: 1.2 }}>
                {userName}
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.8, textTransform: 'capitalize' }}>
                {userRole.replace('_', ' ')}
              </Typography>
            </Box>
            <Tooltip title="Logout">
              <IconButton color="inherit" onClick={handleLogout} sx={{ ml: 0.5 }}>
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Sidebar Drawer */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          whiteSpace: 'nowrap',
          boxSizing: 'border-box',
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            overflowX: 'hidden',
            transition: (theme) =>
              theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: open
                  ? theme.transitions.duration.enteringScreen
                  : theme.transitions.duration.leavingScreen,
              }),
            borderRight: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          },
        }}
      >
        <Toolbar /> {/* Spacer for AppBar */}
        <Box sx={{ overflow: 'hidden', py: 1 }}>
          <List dense disablePadding>
            {NAV_SECTIONS.map((section, idx) => (
              <SidebarSection
                key={idx}
                section={section}
                open={open}
                currentPath={location.pathname}
                onNavigate={navigate}
                userRole={userRole}
              />
            ))}
          </List>
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: `calc(100% - ${drawerWidth}px)`,
          minHeight: '100vh',
          mt: '64px',
          transition: (theme) =>
            theme.transitions.create(['width', 'margin'], {
              easing: theme.transitions.easing.sharp,
              duration: open
                ? theme.transitions.duration.enteringScreen
                : theme.transitions.duration.leavingScreen,
            }),
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}

export default AppLayout;
