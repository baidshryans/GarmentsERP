import { useState, useEffect } from 'react';
import { fetchSystemSettings } from '@/services/apiService';

/**
 * Returns whether spell check / fuzzy search is enabled per system settings.
 * Defaults to false until the setting is loaded from the server.
 */
export function useSpellCheck() {
    const [enabled, setEnabled] = useState(false);

    useEffect(() => {
        fetchSystemSettings().then((res) => {
            if (res.success) setEnabled(!!res.data.spell_check_enabled);
        });
    }, []);

    return enabled;
}
