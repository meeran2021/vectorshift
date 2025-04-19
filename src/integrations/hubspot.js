// /frontend/src/integrations/hubspot.js

import { useState, useEffect } from 'react';
import {
  Box,
  Button,
  CircularProgress
} from '@mui/material';
import axios from 'axios';

export const HubspotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnectClick = async () => {
    try {
      setIsConnecting(true);
      const formData = new FormData();
      formData.append('user_id', user);
      formData.append('org_id', org);

      // Kick off the OAuth flow
      const { data: authURL } = await axios.post(
        'http://localhost:8000/integrations/hubspot/authorize',
        formData
      );

      const popup = window.open(
        authURL,
        'HubSpot Authorization',
        'width=600,height=600'
      );

      // Poll for popup close
      const timer = window.setInterval(() => {
        if (popup?.closed) {
          window.clearInterval(timer);
          handleWindowClosed();
        }
      }, 200);

    } catch (err) {
      setIsConnecting(false);
      alert(err?.response?.data?.detail || err.message);
    }
  };

  const handleWindowClosed = async () => {
    try {
      const formData = new FormData();
      formData.append('user_id', user);
      formData.append('org_id', org);

      const { data: credentials } = await axios.post(
        'http://localhost:8000/integrations/hubspot/credentials',
        formData
      );

      if (credentials) {
        setIntegrationParams(prev => ({
          ...prev,
          credentials,
          type: 'HubSpot'
        }));
        setIsConnected(true);
      }
    } catch (err) {
      alert(err?.response?.data?.detail || err.message);
    } finally {
      setIsConnecting(false);
    }
  };

  useEffect(() => {
    setIsConnected(!!integrationParams?.credentials && integrationParams.type === 'HubSpot');
  }, [integrationParams]);

  return (
    <Box sx={{ mt: 2 }}>
      <Box display="flex" justifyContent="center">
        <Button
          variant="contained"
          color={isConnected ? 'success' : 'primary'}
          onClick={isConnected ? undefined : handleConnectClick}
          disabled={isConnecting || isConnected}
          startIcon={isConnecting ? <CircularProgress size={18} /> : null}
        >
          {isConnected
            ? 'HubSpot Connected'
            : isConnecting
              ? 'Connecting…'
              : 'Connect to HubSpot'}
        </Button>
      </Box>
    </Box>
  );
};
