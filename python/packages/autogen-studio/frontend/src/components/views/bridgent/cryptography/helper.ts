// replacehment for arrayBufferToBase64 function as i didnt add the polyfills for Buffer lmao
export const toB64 = (array: Uint8Array | ArrayBuffer): string => {
    let bytes: Uint8Array;

    if (array instanceof ArrayBuffer) {
        bytes = new Uint8Array(array);
    } else {
        bytes = array;
    }

    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
        const chunk = bytes.subarray(i, i + chunkSize);
        binary += String.fromCharCode.apply(null, Array.from(chunk));
    }
    return btoa(binary);
};

/**
 * Helper function to convert base-64 encoded strings into uint8arrays
 * @param b64encodedString Base-64 encdoed string
 * @returns Uint8Array (BufferLike)
 */
export const toBuffer = (b64encodedString: string) => {
    const binaryString = atob(b64encodedString);
    return Uint8Array.from(binaryString, (char) => char.charCodeAt(0));
};

export function readB64AsUint8(str: string): Uint8Array {
    try {
        return Uint8Array.from(atob(str), (c) => c.charCodeAt(0));
    } catch (error) {
        throw error;
    }
}
