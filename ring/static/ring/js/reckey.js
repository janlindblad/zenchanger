export async function generateRecordKey() {
    const key = await window.crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256, // bits
        },
        true, // extractable: true if you want to export it for encryption
        ["encrypt", "decrypt"]
    );
    return key;
}

export async function generateAndSetEncryptedKey(event) {
    /* The flow is: Generate AES key → Export to raw → Base64 encode → 
       Encrypt with user's public key → Base64 encode again → Store in database. */

    const button = event.target;
    const form = document.getElementById('create-ring-form');
    const encryptedKeyField = document.getElementById('encrypted_key');
    console.log("In generateAndSetEncryptedKey()")

    // Prevent default form submission immediately
    event.preventDefault();
    
    try {
        button.disabled = true;
        button.textContent = 'Generating Key...';
        
        // Generate the AES key
        const key = await generateRecordKey();
        console.log("Generated key", key)
        
        // Export the key to raw format
        const rawKey = await window.crypto.subtle.exportKey("raw", key);
        console.log("Raw key", rawKey)
        const base64Key = btoa(String.fromCharCode(...new Uint8Array(rawKey)));
        console.log("b64 key", base64Key)
        
        // Get user's public key from server or localStorage
        const userPublicKey = await getUserPublicKey();
        console.log("Public key", userPublicKey)
        
        // Encrypt the key with user's public key
        const encoder = new TextEncoder();
        const keyData = encoder.encode(base64Key);
        
        const encryptedData = await window.crypto.subtle.encrypt(
            {
                name: "RSA-OAEP",
            },
            userPublicKey,
            keyData
        );
        console.log("EncryptedData", encryptedData)
        
        // Convert to base64 for storage
        const encryptedBase64 = btoa(String.fromCharCode(...new Uint8Array(encryptedData)));
        
        // Set the encrypted key in the hidden field
        encryptedKeyField.value = encryptedBase64;
        console.log("Encrypted field", encryptedKeyField.value)
        
        // Submit the form
        form.submit();
        
    } catch (error) {
        console.error('Error generating encrypted key:', error);
        alert('Error generating encryption key. Please try again.');
        button.disabled = false;
        button.textContent = 'Create Ring';
        return false;
    }
    
    return false;
}

// Make function available globally
window.generateAndSetEncryptedKey = generateAndSetEncryptedKey;

/**
 * Decrypt the ring's symmetric key using the user's private key
 * @param {string} encryptedBase64Key - Base64 encoded encrypted symmetric key from RingKey
 * @returns {CryptoKey} - The decrypted AES symmetric key
 */
export async function decryptRingKey(encryptedBase64Key) {
    console.log("In decryptRingKey() with key:", encryptedBase64Key);
    try {
        // Get user's private key from localStorage
        const storedPrivateKey = JSON.parse(localStorage.getItem('private_key'));
        if (!storedPrivateKey) {
            throw new Error('No private key found in localStorage');
        }
        console.log("Stored private key structure:", Object.keys(storedPrivateKey));

        // Import the private key
        console.log("Importing private key...");
        const privateKey = await window.crypto.subtle.importKey(
            'jwk',
            storedPrivateKey,
            {
                name: 'RSA-OAEP',
                hash: 'SHA-256'
            },
            false,
            ['decrypt']
        );
        console.log("Private key imported successfully");

        // Convert base64 encrypted key to ArrayBuffer
        console.log("Decoding base64 encrypted key, length:", encryptedBase64Key.length);
        const encryptedData = Uint8Array.from(atob(encryptedBase64Key), c => c.charCodeAt(0));
        console.log("Encrypted data length:", encryptedData.length);

        // Decrypt to get the base64 symmetric key
        console.log("Attempting RSA decryption...");
        const decryptedData = await window.crypto.subtle.decrypt(
            { name: 'RSA-OAEP' },
            privateKey,
            encryptedData
        );
        console.log("RSA decryption successful, decrypted data length:", decryptedData.byteLength);

        // Convert decrypted data back to base64 string
        const base64SymmetricKey = new TextDecoder().decode(decryptedData);
        console.log("Decoded symmetric key (base64):", base64SymmetricKey.substring(0, 20) + "...");

        // Convert base64 back to raw key data
        console.log("Converting base64 to raw key data...");
        const rawKeyData = Uint8Array.from(atob(base64SymmetricKey), c => c.charCodeAt(0));
        console.log("Raw key data length:", rawKeyData.length);

        // Import the symmetric key
        console.log("Importing AES key...");
        const symmetricKey = await window.crypto.subtle.importKey(
            'raw',
            rawKeyData,
            { name: 'AES-GCM' },
            false,
            ['encrypt', 'decrypt']
        );

        console.log("AES key imported successfully");
        return symmetricKey;
    } catch (error) {
        console.error('Detailed error in decryptRingKey:', {
            name: error.name,
            message: error.message,
            stack: error.stack
        });
        throw error;
    }
}

/**
 * Encrypt a string using the ring's symmetric key
 * @param {string} plaintext - The string to encrypt
 * @param {string} encryptedRingKey - Base64 encoded encrypted symmetric key from RingKey
 * @returns {string} - Base64 encoded encrypted data with IV
 */
export async function encryptWithRingKey(plaintext, encryptedRingKey) {
    try {
        // Decrypt the ring's symmetric key
        const symmetricKey = await decryptRingKey(encryptedRingKey);

        // Generate a random IV (Initialization Vector)
        const iv = window.crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV for GCM

        // Convert plaintext to bytes
        const encoder = new TextEncoder();
        const data = encoder.encode(plaintext);

        // Encrypt the data
        const encryptedData = await window.crypto.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            symmetricKey,
            data
        );

        // Combine IV and encrypted data
        const combined = new Uint8Array(iv.length + encryptedData.byteLength);
        combined.set(iv, 0);
        combined.set(new Uint8Array(encryptedData), iv.length);

        // Convert to base64 for storage
        const base64Result = btoa(String.fromCharCode(...combined));
        
        return base64Result;
    } catch (error) {
        console.error('Error encrypting with ring key:', error);
        throw error;
    }
}

/**
 * Decrypt a string using the ring's symmetric key
 * @param {string} encryptedBase64 - Base64 encoded encrypted data with IV
 * @param {string} encryptedRingKey - Base64 encoded encrypted symmetric key from RingKey
 * @returns {string} - The decrypted plaintext
 */
export async function decryptWithRingKey(encryptedBase64, encryptedRingKey) {
    console.log("In decryptWithRingKey()")
    try {
        // Decrypt the ring's symmetric key
        const symmetricKey = await decryptRingKey(encryptedRingKey);
        console.log("Got encoded symmetric key ", symmetricKey)

        // Convert base64 back to bytes
        const combined = Uint8Array.from(atob(encryptedBase64), c => c.charCodeAt(0));

        // Extract IV (first 12 bytes) and encrypted data (rest)
        const iv = combined.slice(0, 12);
        const encryptedData = combined.slice(12);
        console.log("Got iv and encrypted data ", iv, encryptedData)

        // Decrypt the data
        const decryptedData = await window.crypto.subtle.decrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            symmetricKey,
            encryptedData
        );
        console.log("Decrypted data ", decryptedData)

        // Convert back to string
        const decoder = new TextDecoder();
        const plaintext = decoder.decode(decryptedData);

        console.log("Plaintext ", plaintext)
        return plaintext;
    } catch (error) {
        console.error('Error decrypting with ring key:', error);
        throw error;
    }
}

/**
 * Example usage function - encrypt a message for a specific ring
 * @param {string} message - The message to encrypt
 * @param {number} ringId - The ID of the ring
 * @returns {string} - Base64 encoded encrypted message
 */
export async function encryptMessageForRing(message, ringId) {
    try {
        // Get the ring's encrypted key from your backend
        const response = await fetch(`/ring/get_ring_key/${ringId}/`);
        const data = await response.json();
        
        if (!data.encrypted_key) {
            throw new Error('No ring key found');
        }

        return await encryptWithRingKey(message, data.encrypted_key);
    } catch (error) {
        console.error('Error encrypting message for ring:', error);
        throw error;
    }
}

/**
 * Example usage function - decrypt a message from a specific ring
 * @param {string} encryptedMessage - Base64 encoded encrypted message
 * @param {number} ringId - The ID of the ring
 * @returns {string} - The decrypted message
 */
export async function decryptMessageFromRing(encryptedMessage, ringId) {
    try {
        // Get the ring's encrypted key from your backend
        const response = await fetch(`/ring/get_ring_key/${ringId}/`);
        const data = await response.json();
        
        if (!data.encrypted_key) {
            throw new Error('No ring key found');
        }

        return await decryptWithRingKey(encryptedMessage, data.encrypted_key);
    } catch (error) {
        console.error('Error decrypting message from ring:', error);
        throw error;
    }
}

// Add this function to validate your setup
export async function validateKeySetup() {
    try {
        console.log("=== Validating Key Setup ===");

        // Check if private key exists
        const storedPrivateKey = localStorage.getItem('private_key');
        if (!storedPrivateKey) {
            console.error("❌ No private key in localStorage");
            return false;
        }
        
        const privateKeyJWK1 = JSON.parse(storedPrivateKey);
        console.log("✓ Private key found, type:", privateKeyJWK1.kty, "algorithm:", privateKeyJWK1.alg);        

        // Test import private key
        const privateKey = await window.crypto.subtle.importKey(
            'jwk',
            privateKeyJWK1,
            {
                name: 'RSA-OAEP',
                hash: 'SHA-256'
            },
            false,
            ['decrypt']
        );
        console.log("✓ Private key import successful");

        // Add this to your validateKeySetup function
        console.log("=== Checking Key Parameters ===");
        const privateKeyJWK = JSON.parse(localStorage.getItem('private_key'));
        console.log("Private key algorithm:", privateKeyJWK.alg);
        console.log("Private key key type:", privateKeyJWK.kty);
        console.log("Private key usage:", privateKeyJWK.key_ops);

        const response1 = await fetch('/ring/get_user_public_key/');
        const data1 = await response1.json();
        const publicKeyJWK = JSON.parse(data1.public_key);
        console.log("Public key algorithm:", publicKeyJWK.alg);
        console.log("Public key key type:", publicKeyJWK.kty);
        console.log("Public key usage:", publicKeyJWK.key_ops);

        // Check if they match
        if (privateKeyJWK.n !== publicKeyJWK.n) {
            console.error("❌ Public and private keys don't match (different modulus)");
            return false;
        }        

        // Test generate and encrypt/decrypt a sample AES key
        console.log("=== Testing AES Key Generation ===");
        const testAESKey = await generateRecordKey();
        const rawTestKey = await window.crypto.subtle.exportKey("raw", testAESKey);
        const base64TestKey = btoa(String.fromCharCode(...new Uint8Array(rawTestKey)));
        console.log("✓ Test AES key generated, length:", base64TestKey.length);
        
        // Check data size before encryption test
        console.log("=== Checking Data Size ===");
        console.log("Raw AES key size:", rawTestKey.byteLength, "bytes");
        console.log("Base64 AES key size:", base64TestKey.length, "bytes");
        console.log("UTF-8 encoded size:", new TextEncoder().encode(base64TestKey).length, "bytes");

        if (new TextEncoder().encode(base64TestKey).length > 190) {
            console.error("❌ Data too large for RSA-2048 encryption");
            return false;
        }
        
        // Test encryption with public key (simulate what happens during ring creation)
        const response = await fetch('/ring/get_user_public_key/');
        const data = await response.json();
        if (!data.public_key) {
            console.error("❌ No public key from server");
            return false;
        }
        
        const publicKey = await window.crypto.subtle.importKey(
            "jwk",
            JSON.parse(data.public_key),
            {
                name: "RSA-OAEP",
                hash: "SHA-256",
            },
            false,
            ["encrypt"]
        );
        
        const encoder = new TextEncoder();
        const keyData = encoder.encode(base64TestKey);
        const encryptedData = await window.crypto.subtle.encrypt(
            { name: "RSA-OAEP" },
            publicKey,
            keyData
        );
        const encryptedBase64 = btoa(String.fromCharCode(...new Uint8Array(encryptedData)));
        console.log("✓ Test encryption successful, encrypted length:", encryptedBase64.length);
        
        // Test decryption
        const decryptedKey = await decryptRingKey(encryptedBase64);
        console.log("✓ Test decryption successful");
        
        console.log("🎉 All key operations validated successfully!");
        return true;
        
    } catch (error) {
        console.error("❌ Key validation failed:", error);
        return false;
    }
}

// Add this function to reckey.js
export async function testKeyPairCompatibility() {
    try {
        console.log("=== Testing Key Pair Compatibility ===");
        
        // Get private key
        const storedPrivateKey = JSON.parse(localStorage.getItem('private_key'));
        const privateKey = await window.crypto.subtle.importKey(
            'jwk',
            storedPrivateKey,
            { name: 'RSA-OAEP', hash: 'SHA-256' },
            false,
            ['decrypt']
        );
        
        // Get public key from server
        const response = await fetch('/ring/get_user_public_key/');
        const data = await response.json();
        const publicKey = await window.crypto.subtle.importKey(
            "jwk",
            JSON.parse(data.public_key),
            { name: "RSA-OAEP", hash: "SHA-256" },
            false,
            ["encrypt"]
        );
        
        // Test with simple text
        const testMessage = "Hello World";
        const encoder = new TextEncoder();
        const testData = encoder.encode(testMessage);
        
        console.log("Test message size:", testData.length, "bytes");
        
        // Encrypt with public key
        const encrypted = await window.crypto.subtle.encrypt(
            { name: "RSA-OAEP" },
            publicKey,
            testData
        );
        console.log("✓ Public key encryption successful");
        
        // Decrypt with private key
        const decrypted = await window.crypto.subtle.decrypt(
            { name: "RSA-OAEP" },
            privateKey,
            encrypted
        );
        console.log("✓ Private key decryption successful");
        
        const decryptedMessage = new TextDecoder().decode(decrypted);
        if (decryptedMessage === testMessage) {
            console.log("✓ Key pair is compatible!");
            return true;
        } else {
            console.error("❌ Decrypted message doesn't match:", decryptedMessage);
            return false;
        }
        
    } catch (error) {
        console.error("❌ Key pair compatibility test failed:", error);
        return false;
    }
}