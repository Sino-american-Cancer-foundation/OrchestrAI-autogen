import nacl from "tweetnacl";
import { readB64AsUint8, toB64, toBuffer } from "./helper";

/**
 * MORE OR LESS A COPY OF THE PROBILLER IMPLEMENATION. -- 01.21.25
 */

/**
 * Helper function to decode an array buffer back into a JSON
 * @param decryptedBuffer - ArrayBuffer to be read into JSON
 * @returns JSON-object
 */
export function readDecodeBufferIntoJson(decryptedBuffer: ArrayBuffer): any {
    try {
        const uint8Array = new Uint8Array(decryptedBuffer);
        const decoder = new TextDecoder("utf-8");
        const decryptedText = decoder.decode(uint8Array);
        return JSON.parse(decryptedText);
    } catch (error) {
        console.error("Error decoding the buffer: ", error);
        throw error;
    }
}

async function curve25519DecryptAesKey(
    encryptedAesKeyB64: string,
    nonceB64: string,
    ephemeralPublicKeyB64: string
): Promise<string> {
    if (!process.env.GATSBY_TEST_USER_ENCRYPTION_PRIVATE_KEY) {
        throw new Error(
            "Failed to find user's private key when decrypting AES key..."
        );
    }
    const userPriKey = readB64AsUint8(
        process.env.GATSBY_TEST_USER_ENCRYPTION_PRIVATE_KEY
    );
    const encryptedAesKey = toBuffer(encryptedAesKeyB64);
    const nonce = toBuffer(nonceB64);
    const ephemeralPublicKey = toBuffer(ephemeralPublicKeyB64);
    const sharedSecret = nacl.box.before(ephemeralPublicKey, userPriKey);
    const aesKeyUint8 = nacl.secretbox.open(
        encryptedAesKey,
        nonce,
        sharedSecret
    );

    if (!aesKeyUint8) {
        throw new Error("Failed to decrypt aes key");
    }

    return toB64(aesKeyUint8);
}

export async function aesDecryptCurve25519Data(
    encryptedAesKeyB64: string,
    encryptedDataB64: string,
    ivB64: string,
    nonceB64: string,
    ephemeralPublicKeyB64: string
): Promise<ArrayBuffer> {
    try {
        // const userPubKey = readB64AsUint8(import.meta.env.VITE_USER_PUBLIC_KEY);
        console.log(...arguments);
        const rawAesKeyStr = await curve25519DecryptAesKey(
            encryptedAesKeyB64,
            nonceB64,
            ephemeralPublicKeyB64
        );
        const keyBuffer = readB64AsUint8(rawAesKeyStr);

        const aesKey = await crypto.subtle.importKey(
            "raw",
            keyBuffer,
            {
                name: "AES-CBC",
            },
            false,
            ["decrypt"]
        );

        const encryptedData = readB64AsUint8(encryptedDataB64);
        const iv = readB64AsUint8(ivB64);
        return await crypto.subtle.decrypt(
            {
                name: "AES-CBC",
                iv: iv,
            },
            aesKey,
            encryptedData
        );
    } catch (error) {
        console.error(error);
        throw error;
    }
}
