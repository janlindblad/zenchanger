export default function ImportKey() {
  let status = 'loading';

  // Create the DOM structure
  function render() {
    const container = document.createElement('div');
    container.className = 'p-4';
    
    const title = document.createElement('h1');
    title.className = 'text-xl font-bold mb-4';
    title.textContent = 'Import Group Key';
    
    const statusElement = document.createElement('p');
    statusElement.textContent = status;
    statusElement.id = 'status-message';
    
    container.appendChild(title);
    container.appendChild(statusElement);
    
    return container;
  }

  // Function to update status
  function setStatus(newStatus) {
    status = newStatus;
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
      statusElement.textContent = status;
    }
  }

  // Initialize the component
  function init() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    
    if (!token) {
      setStatus('No token found');
      return;
    }

    fetch(`/ring/get_encrypted_key/?token=${token}`)
      .then(res => res.json())
      .then(async ({ encrypted_key }) => {
        const decrypted = await decryptKey(encrypted_key);
        sessionStorage.setItem('group_key', decrypted);
        setStatus('Group key imported successfully!');
      })
      .catch(() => setStatus('Failed to import key'));
  }

  async function decryptKey(base64EncryptedKey) {
    const encBuffer = Uint8Array.from(atob(base64EncryptedKey), c => c.charCodeAt(0));

    const storedPrivateKey = JSON.parse(localStorage.getItem('private_key'));
    const privateKey = await window.crypto.subtle.importKey(
      'jwk',
      storedPrivateKey,
      { name: 'RSA-OAEP', hash: 'SHA-256' },
      false,
      ['decrypt']
    );

    const decryptedBuffer = await window.crypto.subtle.decrypt(
      { name: 'RSA-OAEP' },
      privateKey,
      encBuffer
    );

    return new TextDecoder().decode(decryptedBuffer);
  }

  return {
    render,
    init
  };
}
