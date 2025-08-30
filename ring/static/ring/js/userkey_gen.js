export async function generateAndStoreKeypair() {
  const keyPair = await window.crypto.subtle.generateKey(
    {
      name: 'RSA-OAEP',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256'
    },
    true,
    ['encrypt', 'decrypt']
  )

  const publicKeyJWK = await window.crypto.subtle.exportKey('jwk', keyPair.publicKey)
  const privateKeyJWK = await window.crypto.subtle.exportKey('jwk', keyPair.privateKey)

  localStorage.setItem('private_key', JSON.stringify(privateKeyJWK))

  // Get CSRF token
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                   document.querySelector('meta[name=csrf-token]')?.getAttribute('content');

  const response = await fetch('/ring/store_public_key/', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({ public_key: publicKeyJWK })
  })

  if (!response.ok) {
    throw new Error('Failed to store public key on server');
  }

  return { success: true };
}