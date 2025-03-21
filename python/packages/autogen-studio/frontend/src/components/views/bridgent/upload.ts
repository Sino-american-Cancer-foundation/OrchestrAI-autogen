import sha256 from "fast-sha256";
import {
    aesEncryptData,
    curve25519GenerateCryptoItems,
} from "./cryptography/encrypt";
import { FunctionFlags } from "./types";

function hashJson(jsonData: object): {
    canonicalJson: string;
    hash: string;
} {
    const canonicalJson = JSON.stringify(
        jsonData,
        Object.keys(jsonData).sort()
    );
    const encoder = new TextEncoder();
    const data = encoder.encode(canonicalJson);
    const hashArray = sha256(data);
    return {
        canonicalJson,
        hash: Array.from(hashArray)
            .map((byte) => byte.toString(16).padStart(2, "0"))
            .join(""),
    };
}

export const encryptAndUploadToFireFly = async (
    imageFile: File,
    fullName: string
): Promise<{
    id: string;
    computedHash: string;
}> => {
    if (!imageFile) {
        alert("Please select an image file.");
        throw new Error("No image file selected");
    }

    // Convert image to Base64
    const imageBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(imageFile);
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
    });

    const comboData = {
        image: imageBase64.split(",")[1],
        fullName: fullName,
    };

    const { canonicalJson, hash: computedHash } = hashJson(comboData);

    // Encrypt the data identical to probiller.
    const {
        aesKey,
        encryptedRawAesKeyB64,
        iv,
        ivB64,
        nonceB64,
        ephemeralPublicKeyB64,
    } = await curve25519GenerateCryptoItems();
    const dataToEncrypt = new TextEncoder().encode(canonicalJson);
    const { encryptedDataB64 } = await aesEncryptData(
        aesKey,
        iv,
        dataToEncrypt
    );
    const dataToUpload = {
        encrypted_data_b64: encryptedDataB64,
        encrypted_aes_key_b64: encryptedRawAesKeyB64,
        aes_iv_b64: ivB64,
        curve25519_nonce_b64: nonceB64,
        ephemeral_public_key_b64: ephemeralPublicKeyB64,
    };

    // Names
    const type = "application/json",
        name = "source_content.json";
    const fireflyUrl = process.env.GATSBY_FIREFLY_API_URL;
    if (!fireflyUrl) {
        throw new Error("Failed to find the FireFly URL when uploading...");
    }
    // Structure data
    const jsonStr = JSON.stringify(dataToUpload);
    const blob = new Blob([jsonStr], { type: type });
    const formData = new FormData();
    formData.append("file", blob, name);

    // Upload to FireFly off-chain storage
    const blobUrl = `${fireflyUrl}/api/v1/data`;
    const response = await fetch(blobUrl, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Failed to upload data: ${response.statusText}`);
    }

    const { id } = await response.json();
    // sendPrivateMessage("upload_source_content", id);
    return { id, computedHash };
};

export const invokeFireFlyAPI = async (
    id: string,
    computedHash: string,
    functions: string[],
    address: string
) => {
    if (!functions.length) {
        alert("Please select at least one function.");
        return;
    }

    const payload = {
        input: {
            sourceContentId: id,
            requestedFunctions: functions,
            hashPlainOriginal: computedHash,
        },
        key: address,
        options: {},
    };

    if (!process.env.GATSBY_FIREFLY_CONTRACT_URL) {
        throw new Error("Failed to find Gatsby Contract URL...");
    }
    const contractUrl = process.env.GATSBY_FIREFLY_CONTRACT_URL;
    // const contractUrl =
    //     "https://api.aidtech.ai/api/v1/namespaces/default/apis/test-contract2";
    const response = await fetch(
        `${contractUrl}/invoke/submitTransaction?confirm=true`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                accept: "application/json",
                "Request-Timeout": "2m0s",
            },
            body: JSON.stringify(payload),
        }
    );

    if (!response.ok) {
        throw new Error(`FireFly API call failed: ${response.statusText}`);
        console.log("ERROR: ", response);
    }

    const responseData = await response.json();
};
