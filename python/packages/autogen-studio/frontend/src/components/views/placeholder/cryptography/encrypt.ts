// Essentially a copy of ProBiller version - 01.20.25

import nacl from "tweetnacl";
import { readB64AsUint8, toB64 } from "./helper";

/**
 * MORE OR LESS A COPY OF THE PROBILLER IMPLEMENATION. -- 01.21.25
 */

interface Curve25519CryptoItems {
    aesKey: CryptoKey;
    encryptedRawAesKeyB64: string;
    iv: Uint8Array;
    ivB64: string;
    nonce: Uint8Array;
    nonceB64: string;
    ephemeralPublicKeyB64: string;
}

interface CurveEncryptedAesKeyComponents {
    encryptedKeyB64: string;
    nonce: Uint8Array;
    nonceB64: string;
    ephemeralPublicKeyB64: string;
}

interface EncryptedData {
    encryptedData: ArrayBuffer;
    encryptedDataB64: string;
}

async function curve25519EncryptAesKey(
    aesKey: string
): Promise<CurveEncryptedAesKeyComponents> {
    const aesKeyUint8 = readB64AsUint8(aesKey);

    if (!process.env.GATSBY_TEST_SERVICE_ENCRYPTION_PUBLIC_KEY) {
        throw new Error(
            "Failed to find service encryption public key when encrypting AES key..."
        );
    }

    const servPubKey = readB64AsUint8(
        process.env.GATSBY_TEST_SERVICE_ENCRYPTION_PUBLIC_KEY
    ); // FOR DEMO PURPOSES ONLY
    const {
        publicKey: ephemeralPublicKeyUint8,
        secretKey: ephemeralSecretKeyUint8,
    } = nacl.box.keyPair();

    // Convert to base-64 for testing n' transmission
    const ephemeralPublicKeyB64 = toB64(ephemeralPublicKeyUint8);
    const ephemeralSecretKeyB64 = toB64(ephemeralSecretKeyUint8);

    const sharedSecret = nacl.box.before(servPubKey, ephemeralSecretKeyUint8);
    const nonce = nacl.randomBytes(nacl.box.nonceLength);

    const encryptedKey = nacl.secretbox(aesKeyUint8, nonce, sharedSecret);
    const encryptedKeyB64 = toB64(encryptedKey);
    const nonceB64 = toB64(nonce);

    return { encryptedKeyB64, nonce, nonceB64, ephemeralPublicKeyB64 };
}

export async function curve25519GenerateCryptoItems(): Promise<Curve25519CryptoItems> {
    try {
        const aesKey = await crypto.subtle.generateKey(
            {
                name: "AES-CBC",
                length: 256,
            },
            true,
            ["encrypt", "decrypt"]
        ); // CryptoKey

        const rawAesKey = await crypto.subtle.exportKey("raw", aesKey); // arraybuffer::binary

        const rawAesKeyB64 = toB64(rawAesKey); // b64string
        const {
            encryptedKeyB64: encryptedRawAesKeyB64,
            nonce,
            nonceB64,
            ephemeralPublicKeyB64,
        } = await curve25519EncryptAesKey(rawAesKeyB64);

        const iv = crypto.getRandomValues(new Uint8Array(16));
        const ivB64 = toB64(iv);

        return {
            aesKey,
            encryptedRawAesKeyB64,
            iv,
            ivB64,
            nonce,
            nonceB64,
            ephemeralPublicKeyB64,
        };
    } catch (error) {
        console.error("Error generating cryptography items: ", error);
        throw error;
    }
}

export async function aesEncryptData(
    aesKey: CryptoKey,
    iv: Uint8Array,
    data: Uint8Array
): Promise<EncryptedData> {
    try {
        const encryptedData = await crypto.subtle.encrypt(
            {
                name: "AES-CBC",
                iv: iv,
            },
            aesKey,
            data
        );

        const encryptedDataB64 = toB64(encryptedData);
        return {
            encryptedData,
            encryptedDataB64,
        };
    } catch (error) {
        console.error("Error encrypting data with passed AES-key: ", error);
        throw error;
    }
}
