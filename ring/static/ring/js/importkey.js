// ImportKey.js
import { useEffect, useState } from 'react'

export default function ImportKey() {
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (!token) return setStatus('No token found')

    fetch(`/api/get_encrypted_key?token=${token}`)
      .then(res => res.json())
      .then(async ({ encrypted_key }) => {
        const decrypted = await decryptKey(encrypted_key)
        sessionStorage.setItem('group_key', decrypted)
        setStatus('Group key imported successfully!')
      })
      .catch(() => setStatus('Failed to import key'))
  }, [])

  async function decryptKey(base64EncryptedKey) {
    const encBuffer = Uint8Array.from(atob(base64EncryptedKey), c => c.charCodeAt(0))

    const storedPrivateKey = JSON.parse(localStorage.getItem('private_key'))
    const privateKey = await window.crypto.subtle.importKey(
      'jwk',
      storedPrivateKey,
      { name: 'RSA-OAEP', hash: 'SHA-256' },
      false,
      ['decrypt']
    )

    const decryptedBuffer = await window.crypto.subtle.decrypt(
      { name: 'RSA-OAEP' },
      privateKey,
      encBuffer
    )

    return new TextDecoder().decode(decryptedBuffer)
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Import Group Key</h1>
      <p>{status}</p>
    </div>
  )
}
