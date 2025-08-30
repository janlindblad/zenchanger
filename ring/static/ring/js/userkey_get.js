    export async function getUserPublicKey() {
        try {
            const response = await fetch('/ring/get_user_public_key/', {
                credentials: 'include',  // Include cookies for authentication
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',  // Indicates AJAX request
                }
            });
            
            if (response.status === 404) {
                throw new Error('User not authenticated or no public key found');
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.public_key) {
                return await window.crypto.subtle.importKey(
                    "jwk",
                    JSON.parse(data.public_key),
                    {
                        name: "RSA-OAEP",
                        hash: "SHA-256",
                    },
                    false,
                    ["encrypt"]
                );
            }
            throw new Error(data.error || 'No public key found');
        } catch (error) {
            console.error('Error fetching public key from server:', error);
            throw error;
        }
    }
window.getUserPublicKey = getUserPublicKey;