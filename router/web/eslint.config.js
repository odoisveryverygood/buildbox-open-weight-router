import js from '@eslint/js';
import ts from 'typescript-eslint';
export default ts.config({ignores: ['src/generated/**']}, js.configs.recommended, ...ts.configs.recommended);
