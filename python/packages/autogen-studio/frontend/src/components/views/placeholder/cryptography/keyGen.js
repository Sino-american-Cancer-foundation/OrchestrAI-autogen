import { generateMnemonic, mnemonicToSeed, mnemonicToSeedSync } from "bip39";
import nacl from "tweetnacl";
/**
 * COPIED AND EDITED FROM PROBILLER VERISON -- 01.20.25.
 * CONTEXT: I WAS JUST RUNNING THIS FROM CONSOLE. ie `node keyGen.js` to get some random keypairs for testing
 */

async function generateDeterministicCurve25519Keys(mnemonic) {
    // Normalize mnemonic by cutting off white space and lower-caseing everything
    const normalizedMnemonic = mnemonic.trim().toLowerCase();

    // Convert the mnemonic to a seed using default bip39
    const seed = mnemonicToSeedSync(normalizedMnemonic, "");

    // Take the first 32 bytes of the seed for the private key
    const privateKey = seed.subarray(0, 32);

    // Generate key-pair
    const keyPair = nacl.box.keyPair.fromSecretKey(privateKey);

    // Convert to base-64
    const publicKeyBase64 = Buffer.from(keyPair.publicKey).toString("base64");
    const secretKeyBase64 = Buffer.from(keyPair.secretKey).toString("base64");

    const objectToPrint = {
        mnemonic: normalizedMnemonic,
        publicKeyBase64: publicKeyBase64,
        privateKeyBase64: secretKeyBase64,
    };

    console.log(JSON.stringify(objectToPrint, null, 2));

    return { publicKeyBase64, secretKeyBase64 };
}

async function generateMnemonicAndCurve25519Keys() {
    const mnemonic = generateMnemonic(128); // 12 words
    console.log("Mnemonic: ", mnemonic);
    const { publicKeyBase64, secretKeyBase64 } =
        await generateDeterministicCurve25519Keys(mnemonic);
    // console.log(mnemonic);
    return { mnemonic, publicKeyBase64, secretKeyBase64 };
}

function main() {
    console.log(generateMnemonicAndCurve25519Keys());
}

main();
