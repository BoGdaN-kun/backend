import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container, Grid, Paper, Typography, Box, Button, TextField,
    List, ListItem, ListItemText, IconButton, Divider,
    CircularProgress, Alert, Snackbar, Dialog, DialogActions,
    DialogContent, DialogContentText, DialogTitle, Fab, AppBar, Toolbar
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import PlaylistAddIcon from '@mui/icons-material/PlaylistAdd';
import ClearIcon from '@mui/icons-material/Clear';



const API_BASE_URL_TRADING_APP = "http://localhost:5000";

const getAuthToken = () => localStorage.getItem('authToken');

async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `Request failed: ${response.status}` }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        if (response.status === 204 || response.headers.get("content-length") === "0") {
            return null;
        }
        return response.json();
    } catch (error) {
        console.error(`API call error for ${url}:`, error.message);
        throw error;
    }
}

export default function WatchlistPage() {
    const [watchlists, setWatchlists] = useState([]);
    const [selectedWatchlist, setSelectedWatchlist] = useState(null);
    const [newWatchlistName, setNewWatchlistName] = useState('');
    const [symbolToAdd, setSymbolToAdd] = useState('');

    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });

    const [deleteConfirm, setDeleteConfirm] = useState({ open: false, type: null, id: null, name: '' });

    const navigate = useNavigate();

    const fetchWatchlists = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists`);
            setWatchlists(Array.isArray(data) ? data : []);
        } catch (err) {
            setError(err.message || "Failed to fetch watchlists.");
            setWatchlists([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchWatchlists();
    }, [fetchWatchlists]);

    const handleCreateWatchlist = async (e) => {
        e.preventDefault();
        if (!newWatchlistName.trim()) {
            setSnackbar({ open: true, message: "Watchlist name cannot be empty.", severity: 'warning' });
            return;
        }
        setIsLoading(true);
        try {
            await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists`, {
                method: 'POST',
                body: JSON.stringify({ name: newWatchlistName }),
            });
            setNewWatchlistName('');
            fetchWatchlists();
            setSnackbar({ open: true, message: `Watchlist '${newWatchlistName}' created.`, severity: 'success' });
        } catch (err) {
            setError(err.message || "Failed to create watchlist.");
            setSnackbar({ open: true, message: err.message || "Failed to create watchlist.", severity: 'error' });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelectWatchlist = async (watchlistId) => {
        if (selectedWatchlist?.id === watchlistId) {
            setSelectedWatchlist(null);
            return;
        }
        setIsLoading(true);
        try {
            const data = await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists/${watchlistId}`);
            setSelectedWatchlist(data);
        } catch (err) {
            setError(err.message || "Failed to fetch watchlist details.");
            setSnackbar({ open: true, message: err.message || "Failed to fetch watchlist details.", severity: 'error' });
            setSelectedWatchlist(null);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAddSymbol = async (e) => {
        e.preventDefault();
        if (!selectedWatchlist || !symbolToAdd.trim()) {
            setSnackbar({ open: true, message: "Select a watchlist and enter a symbol.", severity: 'warning' });
            return;
        }
        setIsLoading(true);
        try {
            await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists/${selectedWatchlist.id}/items`, {
                method: 'POST',
                body: JSON.stringify({ symbol: symbolToAdd.toUpperCase() }),
            });
            setSymbolToAdd('');
            handleSelectWatchlist(selectedWatchlist.id);
            setSnackbar({ open: true, message: `Symbol '${symbolToAdd.toUpperCase()}' added to ${selectedWatchlist.name}.`, severity: 'success' });
        } catch (err) {
            setError(err.message || "Failed to add symbol.");
            setSnackbar({ open: true, message: err.message || "Failed to add symbol.", severity: 'error' });
        } finally {
            setIsLoading(false);
        }
    };

    const openDeleteConfirm = (type, id, name) => {
        setDeleteConfirm({ open: true, type, id, name });
    };

    const closeDeleteConfirm = () => {
        setDeleteConfirm({ open: false, type: null, id: null, name: '' });
    };

    const confirmDeleteItem = async () => {
        if (!deleteConfirm.id || !deleteConfirm.type) return;
        setIsLoading(true);
        try {
            if (deleteConfirm.type === 'watchlist') {
                await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists/${deleteConfirm.id}`, { method: 'DELETE' });
                fetchWatchlists();
                if (selectedWatchlist?.id === deleteConfirm.id) setSelectedWatchlist(null);
                setSnackbar({ open: true, message: `Watchlist '${deleteConfirm.name}' deleted.`, severity: 'success' });
            } else if (deleteConfirm.type === 'item' && selectedWatchlist) {
                await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/watchlists/${selectedWatchlist.id}/items/${deleteConfirm.id}`, { method: 'DELETE' });
                handleSelectWatchlist(selectedWatchlist.id);
                setSnackbar({ open: true, message: `Symbol '${deleteConfirm.name}' removed from ${selectedWatchlist.name}.`, severity: 'success' });
            }
        } catch (err) {
            setError(err.message || `Failed to delete ${deleteConfirm.type}.`);
            setSnackbar({ open: true, message: err.message || `Failed to delete ${deleteConfirm.type}.`, severity: 'error' });
        } finally {
            setIsLoading(false);
            closeDeleteConfirm();
        }
    };

    const handleSymbolClick = (symbol) => {
        navigate(`/stock/${symbol}`);
    };

    const handleCloseSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    return (
        <>
            <AppBar position="static" sx={{ mb: 3 }}>
                <Toolbar>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        My Watchlists
                    </Typography>
                </Toolbar>
            </AppBar>
            <Container maxWidth="lg">
                <Grid container spacing={3}>
                    {/* Column for Watchlist List and Create New */}
                    <Grid item xs={12} md={4}>
                        <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>Create New Watchlist</Typography>
                            <Box component="form" onSubmit={handleCreateWatchlist} sx={{ display: 'flex', gap: 1 }}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label="New Watchlist Name"
                                    value={newWatchlistName}
                                    onChange={(e) => setNewWatchlistName(e.target.value)}
                                    variant="outlined"
                                />
                                <Button type="submit" variant="contained" color="primary" startIcon={<AddIcon />} disabled={isLoading}>
                                    Create
                                </Button>
                            </Box>
                        </Paper>

                        <Paper elevation={2} sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>Your Watchlists</Typography>
                            {isLoading && watchlists.length === 0 && <CircularProgress />}
                            {!isLoading && error && <Alert severity="error" sx={{mb:1}}>{error}</Alert>}
                            {watchlists.length === 0 && !isLoading && !error && <Typography color="text.secondary">No watchlists yet. Create one!</Typography>}
                            <List dense>
                                {watchlists.map((wl) => (
                                    <React.Fragment key={wl.id}>
                                        <ListItem
                                            secondaryAction={
                                                <>
                                                    <IconButton edge="end" aria-label="view" onClick={() => handleSelectWatchlist(wl.id)} color={selectedWatchlist?.id === wl.id ? "primary" : "default"} title="View Items">
                                                        <VisibilityIcon />
                                                    </IconButton>
                                                    <IconButton edge="end" aria-label="delete" onClick={() => openDeleteConfirm('watchlist', wl.id, wl.name)} title="Delete Watchlist">
                                                        <DeleteIcon color="error" />
                                                    </IconButton>
                                                </>
                                            }
                                            sx={{ bgcolor: selectedWatchlist?.id === wl.id ? 'action.selected' : 'transparent', borderRadius: 1, mb:0.5}}
                                        >
                                            <ListItemText primary={wl.name} primaryTypographyProps={{ fontWeight: selectedWatchlist?.id === wl.id ? 'bold' : 'normal' }} />
                                        </ListItem>
                                        <Divider component="li" sx={{my:0.5}}/>
                                    </React.Fragment>
                                ))}
                            </List>
                        </Paper>
                    </Grid>

                    {/* Column for Selected Watchlist Details */}
                    <Grid item xs={12} md={8}>
                        {selectedWatchlist ? (
                            <Paper elevation={2} sx={{ p: 2, height: '100%' }}>
                                <Typography variant="h5" gutterBottom sx={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                                    {selectedWatchlist.name}
                                    <Button size="small" variant="outlined" onClick={() => setSelectedWatchlist(null)} startIcon={<ClearIcon/>}>Close View</Button>
                                </Typography>

                                <Box component="form" onSubmit={handleAddSymbol} sx={{ display: 'flex', gap: 1, mb: 2 }}>
                                    <TextField
                                        fullWidth
                                        size="small"
                                        label="Stock Symbol (e.g., AAPL)"
                                        value={symbolToAdd}
                                        onChange={(e) => setSymbolToAdd(e.target.value)}
                                        variant="outlined"
                                    />
                                    <Button type="submit" variant="contained" color="secondary" startIcon={<PlaylistAddIcon />} disabled={isLoading}>
                                        Add Symbol
                                    </Button>
                                </Box>
                                <Divider sx={{my:1}}/>
                                {isLoading && selectedWatchlist.items === undefined && <CircularProgress />}
                                {selectedWatchlist.items && selectedWatchlist.items.length > 0 ? (
                                    <List dense>
                                        {selectedWatchlist.items.map((item) => (
                                            <ListItem
                                                key={item.id}
                                                secondaryAction={
                                                    <IconButton edge="end" aria-label="remove item" onClick={() => openDeleteConfirm('item', item.id, item.symbol)} title={`Remove ${item.symbol}`}>
                                                        <DeleteIcon fontSize="small" color="action"/>
                                                    </IconButton>
                                                }
                                                button
                                                onClick={() => handleSymbolClick(item.symbol)}
                                                title={`View details for ${item.symbol}`}
                                                sx={{ '&:hover': { bgcolor: 'action.hover' }, borderRadius: 1 }}
                                            >
                                                <ListItemText primary={item.symbol} />
                                                <ArrowForwardIosIcon fontSize="small" color="action"/>
                                            </ListItem>
                                        ))}
                                    </List>
                                ) : (
                                    !isLoading && <Typography color="text.secondary" sx={{mt:2}}>No symbols in this watchlist yet.</Typography>
                                )}
                            </Paper>
                        ) : (
                            <Paper elevation={2} sx={{ p: 3, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Typography variant="h6" color="text.secondary">Select a watchlist to view its items.</Typography>
                            </Paper>
                        )}
                    </Grid>
                </Grid>

                {/* Snackbar for notifications */}
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={4000}
                    onClose={handleCloseSnackbar}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                >
                    <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
                        {snackbar.message}
                    </Alert>
                </Snackbar>

                {/* Confirmation Dialog for Deletions */}
                <Dialog open={deleteConfirm.open} onClose={closeDeleteConfirm}>
                    <DialogTitle>Confirm Deletion</DialogTitle>
                    <DialogContent>
                        <DialogContentText>
                            Are you sure you want to delete {deleteConfirm.type === 'item' ? `symbol '${deleteConfirm.name}'` : `watchlist '${deleteConfirm.name}'`}?
                            {deleteConfirm.type === 'watchlist' && " This will also remove all items within it."}
                        </DialogContentText>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={closeDeleteConfirm}>Cancel</Button>
                        <Button onClick={confirmDeleteItem} color="error" disabled={isLoading}>
                            {isLoading ? <CircularProgress size={20}/> : "Delete"}
                        </Button>
                    </DialogActions>
                </Dialog>

            </Container>
        </>
    );
}
