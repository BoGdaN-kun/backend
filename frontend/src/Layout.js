import React from 'react';
import { AppBar, Toolbar, Typography, Box, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Divider } from '@mui/material';
import { Link, useLocation } from 'react-router-dom';


import ShowChartIcon from '@mui/icons-material/ShowChart';
import InsightsIcon from '@mui/icons-material/Insights';
import PlaylistPlayIcon from '@mui/icons-material/PlaylistPlay';
import { Outlet } from 'react-router-dom';

const drawerWidth = 240;


const navItems = [
    { text: 'Portfolio', path: '/portfolio', icon: <ShowChartIcon /> },
    { text: 'Simulator', path: '/simulator', icon: <InsightsIcon /> },
    { text: 'Watchlist', path: '/watchlists', icon: <PlaylistPlayIcon /> },
    { text: 'LoginPage', path: '/login', icon: <PlaylistPlayIcon /> },
];

export default function Layout() {
    const location = useLocation();

    return (
        <Box sx={{ display: 'flex' }}>
            {/* Top Application Bar */}
            <AppBar
                position="fixed"
                sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
            >
                <Toolbar>
                    <Typography variant="h6" noWrap component="div">
                        Trading App
                    </Typography>
                </Toolbar>
            </AppBar>

            {/* Left Side Navigation Drawer */}
            <Drawer
                variant="permanent"
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' },
                }}
            >

                <Toolbar />
                <Box sx={{ overflow: 'auto' }}>
                    <List>
                        {navItems.map((item) => (
                            <ListItem key={item.text} disablePadding>
                                <ListItemButton
                                    component={Link}
                                    to={item.path}

                                    selected={location.pathname.startsWith(item.path)}
                                >
                                    <ListItemIcon>{item.icon}</ListItemIcon>
                                    <ListItemText primary={item.text} />
                                </ListItemButton>
                            </ListItem>
                        ))}
                    </List>
                </Box>
            </Drawer>

            {/* Main Content Area */}
            <Box
                component="main"
                sx={{ flexGrow: 1, bgcolor: 'grey.100', p: 3, height: '100vh', overflow: 'auto' }}
            >

                <Toolbar />
                <Outlet />
            </Box>
        </Box>
    );
}