import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import '../../core/constants/specialties.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/validators.dart';
import '../../providers/auth_provider.dart';
import '../auth/email_verification_screen.dart';

class DoctorRegistrationScreen extends StatefulWidget {
  const DoctorRegistrationScreen({super.key});

  @override
  State<DoctorRegistrationScreen> createState() => _DoctorRegistrationScreenState();
}

class _DoctorRegistrationScreenState extends State<DoctorRegistrationScreen> {
  int _currentStep = 0;

  // Step 1 Controllers (Personal)
  final _personalFormKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  // Step 2 Controllers (Professional)
  final _profFormKey = GlobalKey<FormState>();
  String? _selectedSpecialty;
  final _medRegNumController = TextEditingController();
  final _qualificationsController = TextEditingController();
  final _hospitalClinicController = TextEditingController();
  final _experienceYearsController = TextEditingController(text: '0');
  final _bioController = TextEditingController();

  // Step 3 (Documents)
  PlatformFile? _identityFile;
  PlatformFile? _registrationFile;
  PlatformFile? _qualificationFile;
  String? _documentError;

  static const int maxFileSize = 5 * 1024 * 1024; // 5MB

  @override
  void dispose() {
    _fullNameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _medRegNumController.dispose();
    _qualificationsController.dispose();
    _hospitalClinicController.dispose();
    _experienceYearsController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  Future<void> _pickDocument({
    required String docKey,
    required Function(PlatformFile file) onSelected,
  }) async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
      );

      if (files.isNotEmpty) {
        final file = files.first;
        final fileSize = file.lengthSync() ?? (await file.length()) ?? 0;
        if (fileSize > maxFileSize) {
          setState(() {
            _documentError = 'File "${file.name}" exceeds maximum allowed size of 5MB.';
          });
          return;
        }

        setState(() {
          _documentError = null;
          onSelected(file);
        });
      }
    } catch (e) {
      setState(() {
        _documentError = 'Unable to pick document. Please try again.';
      });
    }
  }

  void _nextStep() {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    if (_currentStep == 0) {
      if (!_personalFormKey.currentState!.validate()) return;
      setState(() => _currentStep = 1);
    } else if (_currentStep == 1) {
      if (!_profFormKey.currentState!.validate()) return;
      if (_selectedSpecialty == null || _selectedSpecialty!.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Please select your medical specialty.'),
            backgroundColor: AppTheme.error,
          ),
        );
        return;
      }
      setState(() => _currentStep = 2);
    } else if (_currentStep == 2) {
      if (_identityFile == null || _registrationFile == null || _qualificationFile == null) {
        setState(() {
          _documentError = 'Please upload all 3 required verification documents.';
        });
        return;
      }
      setState(() {
        _documentError = null;
        _currentStep = 3;
      });
    }
  }

  void _previousStep() {
    if (_currentStep > 0) {
      setState(() => _currentStep--);
    } else {
      Navigator.of(context).pop();
    }
  }

  Future<http.MultipartFile> _createMultipartFile(String fieldName, PlatformFile file) async {
    final bytes = await file.readAsBytes();
    return http.MultipartFile.fromBytes(
      fieldName,
      bytes,
      filename: file.name,
    );
  }

  Future<void> _handleSubmit() async {
    final authProvider = context.read<AuthProvider>();
    authProvider.clearError();

    final identityPart = await _createMultipartFile('identityDocument', _identityFile!);
    final regPart = await _createMultipartFile('medicalRegistrationDocument', _registrationFile!);
    final qualPart = await _createMultipartFile('qualificationDocument', _qualificationFile!);

    final expYears = int.tryParse(_experienceYearsController.text.trim()) ?? 0;

    final success = await authProvider.registerDoctor(
      fullName: _fullNameController.text.trim(),
      email: _emailController.text.trim(),
      phone: _phoneController.text.trim(),
      password: _passwordController.text,
      specialty: _selectedSpecialty!,
      medicalRegistrationNumber: _medRegNumController.text.trim(),
      qualifications: _qualificationsController.text.trim(),
      hospitalOrClinic: _hospitalClinicController.text.trim(),
      experienceYears: expYears,
      bio: _bioController.text.trim().isNotEmpty ? _bioController.text.trim() : null,
      identityDocument: identityPart,
      medicalRegistrationDocument: regPart,
      qualificationDocument: qualPart,
    );

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.success,
          content: Text('Doctor application submitted! Please verify your email with the OTP code.'),
          duration: Duration(seconds: 4),
        ),
      );

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => EmailVerificationScreen(
            email: _emailController.text.trim(),
            isDoctor: true,
          ),
        ),
      );
    }
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.isLoading;
    final errorMessage = authProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Doctor Registration'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: isLoading ? null : _previousStep,
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Progress Indicator
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              color: Colors.white,
              child: Row(
                children: [
                  _buildStepBubble(0, 'Personal'),
                  _buildStepConnector(0),
                  _buildStepBubble(1, 'Professional'),
                  _buildStepConnector(1),
                  _buildStepBubble(2, 'Documents'),
                  _buildStepConnector(2),
                  _buildStepBubble(3, 'Review'),
                ],
              ),
            ),
            const Divider(height: 1),

            // Form Body
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (errorMessage != null) ...[
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppTheme.errorContainer,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 20),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                errorMessage,
                                style: const TextStyle(
                                  color: AppTheme.error,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],

                    if (_currentStep == 0) _buildStep1Personal(),
                    if (_currentStep == 1) _buildStep2Professional(),
                    if (_currentStep == 2) _buildStep3Documents(),
                    if (_currentStep == 3) _buildStep4Review(),
                  ],
                ),
              ),
            ),

            // Bottom Navigation Controls
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, -4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  if (_currentStep > 0) ...[
                    Expanded(
                      flex: 1,
                      child: OutlinedButton(
                        onPressed: isLoading ? null : _previousStep,
                        child: const Text('Back'),
                      ),
                    ),
                    const SizedBox(width: 12),
                  ],
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      key: const Key('doctor_reg_continue_button'),
                      onPressed: isLoading
                          ? null
                          : () {
                              if (_currentStep < 3) {
                                _nextStep();
                              } else {
                                _handleSubmit();
                              }
                            },
                      child: isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.5,
                                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            )
                          : Text(_currentStep < 3 ? 'Continue' : 'Submit Application'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepBubble(int stepIndex, String title) {
    final isDone = _currentStep > stepIndex;
    final isCurrent = _currentStep == stepIndex;

    Color color;
    if (isDone) {
      color = AppTheme.success;
    } else if (isCurrent) {
      color = AppTheme.primary;
    } else {
      color = AppTheme.textMuted.withValues(alpha: 0.3);
    }

    return Column(
      children: [
        CircleAvatar(
          radius: 14,
          backgroundColor: color,
          child: isDone
              ? const Icon(Icons.check, size: 16, color: Colors.white)
              : Text(
                  '${stepIndex + 1}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: isCurrent ? Colors.white : AppTheme.textSecondary,
                  ),
                ),
        ),
        const SizedBox(height: 4),
        Text(
          title,
          style: TextStyle(
            fontSize: 10,
            fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal,
            color: isCurrent ? AppTheme.primary : AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildStepConnector(int stepIndex) {
    final isDone = _currentStep > stepIndex;
    return Expanded(
      child: Container(
        height: 2,
        margin: const EdgeInsets.only(bottom: 16),
        color: isDone ? AppTheme.success : AppTheme.textMuted.withValues(alpha: 0.2),
      ),
    );
  }

  // STEP 1: Personal Information
  Widget _buildStep1Personal() {
    return Form(
      key: _personalFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Personal Information',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 6),
          const Text(
            'Enter your full name and official contact credentials.',
            style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 20),
          TextFormField(
            key: const Key('doctor_full_name_input'),
            controller: _fullNameController,
            textCapitalization: TextCapitalization.words,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Full Name (with Dr. prefix)',
              hintText: 'Dr. Kasun Perera',
              prefixIcon: Icon(Icons.person_outline),
            ),
            validator: (v) => Validators.validateFullName(v),
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const Key('doctor_email_input'),
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Email Address',
              hintText: 'doctor@example.com',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            validator: (v) => Validators.validateEmail(v),
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const Key('doctor_phone_input'),
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Mobile Phone',
              hintText: '0771234567 or +94771234567',
              prefixIcon: Icon(Icons.phone_outlined),
            ),
            validator: (v) => Validators.validatePhone(v),
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const Key('doctor_password_input'),
            controller: _passwordController,
            obscureText: _obscurePassword,
            textInputAction: TextInputAction.next,
            decoration: InputDecoration(
              labelText: 'Password',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                icon: Icon(_obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
            validator: (v) => Validators.validatePassword(v),
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const Key('doctor_confirm_password_input'),
            controller: _confirmPasswordController,
            obscureText: _obscureConfirmPassword,
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              labelText: 'Confirm Password',
              prefixIcon: const Icon(Icons.lock_clock_outlined),
              suffixIcon: IconButton(
                icon: Icon(_obscureConfirmPassword ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                onPressed: () => setState(() => _obscureConfirmPassword = !_obscureConfirmPassword),
              ),
            ),
            validator: (v) => Validators.validateConfirmPassword(v, _passwordController.text),
          ),
        ],
      ),
    );
  }

  // STEP 2: Professional Information
  Widget _buildStep2Professional() {
    return Form(
      key: _profFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Professional Information',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 6),
          const Text(
            'Provide your medical credentials and clinical affiliations.',
            style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 20),

          // Specialty dropdown
          DropdownButtonFormField<String>(
            key: const Key('doctor_specialty_select'),
            initialValue: _selectedSpecialty,
            decoration: const InputDecoration(
              labelText: 'Medical Specialty',
              prefixIcon: Icon(Icons.medical_services_outlined),
            ),
            items: Specialties.list.map((specialty) {
              return DropdownMenuItem<String>(
                value: specialty,
                child: Text(specialty),
              );
            }).toList(),
            onChanged: (val) {
              setState(() {
                _selectedSpecialty = val;
              });
            },
            validator: (v) => (v == null || v.isEmpty) ? 'Please select a specialty.' : null,
          ),
          const SizedBox(height: 16),

          TextFormField(
            key: const Key('doctor_med_reg_num_input'),
            controller: _medRegNumController,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Medical Registration Number (SLMC)',
              hintText: 'e.g. SLMC-12345',
              prefixIcon: Icon(Icons.badge_outlined),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'Medical registration number is required.';
              }
              if (v.trim().length < 2) {
                return 'Must be at least 2 characters.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          TextFormField(
            key: const Key('doctor_qualifications_input'),
            controller: _qualificationsController,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Qualifications',
              hintText: 'e.g. MBBS (Colombo), MD (Cardiology)',
              prefixIcon: Icon(Icons.school_outlined),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'Qualifications are required.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          TextFormField(
            key: const Key('doctor_hospital_clinic_input'),
            controller: _hospitalClinicController,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Hospital or Clinic',
              hintText: 'e.g. National Hospital of Sri Lanka',
              prefixIcon: Icon(Icons.local_hospital_outlined),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'Hospital or clinic is required.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          TextFormField(
            key: const Key('doctor_experience_years_input'),
            controller: _experienceYearsController,
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.next,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: const InputDecoration(
              labelText: 'Years of Experience',
              hintText: 'e.g. 8',
              prefixIcon: Icon(Icons.work_history_outlined),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'Experience years are required.';
              }
              final exp = int.tryParse(v.trim());
              if (exp == null || exp < 0 || exp > 70) {
                return 'Must be between 0 and 70.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          TextFormField(
            key: const Key('doctor_bio_input'),
            controller: _bioController,
            maxLines: 3,
            maxLength: 1000,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              labelText: 'Professional Bio (Optional)',
              hintText: 'Brief summary of your clinical experience and interests...',
              alignLabelWithHint: true,
              prefixIcon: Icon(Icons.notes_outlined),
            ),
          ),
        ],
      ),
    );
  }

  // STEP 3: Verification Documents
  Widget _buildStep3Documents() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Verification Documents',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
        ),
        const SizedBox(height: 6),
        const Text(
          'Upload official documents for administrative verification. PDF, JPG, JPEG, and PNG files up to 5MB are accepted.',
          style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 20),

        if (_documentError != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.errorContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                const Icon(Icons.error_outline, color: AppTheme.error, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _documentError!,
                    style: const TextStyle(color: AppTheme.error, fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],

        _buildDocumentUploadCard(
          title: '1. Identity Document',
          subtitle: 'National Identity Card (NIC) or Passport',
          file: _identityFile,
          docKey: 'identity_doc_picker',
          onPick: () => _pickDocument(
            docKey: 'identity',
            onSelected: (f) => _identityFile = f,
          ),
        ),
        const SizedBox(height: 16),

        _buildDocumentUploadCard(
          title: '2. Medical Registration Document',
          subtitle: 'SLMC Registration Certificate or Practicing License',
          file: _registrationFile,
          docKey: 'med_reg_doc_picker',
          onPick: () => _pickDocument(
            docKey: 'registration',
            onSelected: (f) => _registrationFile = f,
          ),
        ),
        const SizedBox(height: 16),

        _buildDocumentUploadCard(
          title: '3. Qualification Certificate',
          subtitle: 'Primary Medical Degree or Postgraduate Board Certification',
          file: _qualificationFile,
          docKey: 'qual_doc_picker',
          onPick: () => _pickDocument(
            docKey: 'qualification',
            onSelected: (f) => _qualificationFile = f,
          ),
        ),
      ],
    );
  }

  Widget _buildDocumentUploadCard({
    required String title,
    required String subtitle,
    required PlatformFile? file,
    required String docKey,
    required VoidCallback onPick,
  }) {
    final hasFile = file != null;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasFile ? AppTheme.success.withValues(alpha: 0.5) : AppTheme.border,
          width: hasFile ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                hasFile ? Icons.check_circle : Icons.upload_file_outlined,
                color: hasFile ? AppTheme.success : AppTheme.primary,
                size: 22,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: AppTheme.textPrimary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          if (hasFile) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.attach_file, size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '${file.name} (${_formatFileSize(file.lengthSync() ?? 0)})',
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                    ),
                  ),
                  TextButton(
                    onPressed: onPick,
                    child: const Text('Change', style: TextStyle(fontSize: 12)),
                  ),
                ],
              ),
            ),
          ] else ...[
            OutlinedButton.icon(
              key: Key(docKey),
              onPressed: onPick,
              icon: const Icon(Icons.attach_file, size: 18),
              label: const Text('Select File'),
            ),
          ],
        ],
      ),
    );
  }

  // STEP 4: Review
  Widget _buildStep4Review() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Review Your Application',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
        ),
        const SizedBox(height: 6),
        const Text(
          'Please verify your submitted information. Password will be stored securely.',
          style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 20),

        _buildReviewSection(
          title: 'Personal Details',
          stepToEdit: 0,
          items: {
            'Full Name': _fullNameController.text,
            'Email': _emailController.text,
            'Phone': _phoneController.text,
          },
        ),
        const SizedBox(height: 16),

        _buildReviewSection(
          title: 'Professional Details',
          stepToEdit: 1,
          items: {
            'Specialty': _selectedSpecialty ?? '',
            'Registration No.': _medRegNumController.text,
            'Qualifications': _qualificationsController.text,
            'Hospital/Clinic': _hospitalClinicController.text,
            'Experience': '${_experienceYearsController.text} Years',
            if (_bioController.text.trim().isNotEmpty) 'Bio': _bioController.text,
          },
        ),
        const SizedBox(height: 16),

        _buildReviewSection(
          title: 'Attached Documents',
          stepToEdit: 2,
          items: {
            'Identity': _identityFile?.name ?? 'Not selected',
            'Registration': _registrationFile?.name ?? 'Not selected',
            'Qualification': _qualificationFile?.name ?? 'Not selected',
          },
        ),
        const SizedBox(height: 20),

        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.primaryLight.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primary.withValues(alpha: 0.3)),
          ),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, color: AppTheme.primary, size: 20),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'After submitting, you will verify your email via a 6-digit OTP code. Your application will then enter administrative review before clinical features are activated.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.4),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildReviewSection({
    required String title,
    required int stepToEdit,
    required Map<String, String> items,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppTheme.textPrimary),
              ),
              InkWell(
                onTap: () => setState(() => _currentStep = stepToEdit),
                child: const Text(
                  'Edit',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.primary),
                ),
              ),
            ],
          ),
          const Divider(height: 16),
          ...items.entries.map((entry) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4.0),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 120,
                    child: Text(
                      entry.key,
                      style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      entry.value,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: AppTheme.textPrimary),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
